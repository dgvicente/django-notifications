# coding=utf-8
import logging
from django.utils import timezone
from django.utils.module_loading import import_by_path
from django.contrib.auth.models import User
from django.db.models import Count
from celery import shared_task as task
from .utils import get_attendants_from_config

logger = logging.getLogger(__name__)


@task(name='notifications.send_immediate')
def send_notification(event):
    from .models import Transport, EventAttendantsConfig, Subscription, NotificationTemplateConfig

    #TODO Cache!!!!
    transports = Transport.objects.all()

    for transport in transports:
        # Obtain attendants for current transport for this event_type
        try:
            attendants_config = EventAttendantsConfig.objects.get(transport=transport, event_type=event.type)
            get_attendants_methods = attendants_config.get_attendants_methods
            attendants = get_attendants_from_config(get_attendants_methods, event)
        except EventAttendantsConfig.DoesNotExist:
            get_attendants_methods = None
            attendants = dict()


        #Obtaining the actual method that sends the notification
        transport_class = import_by_path(transport.cls)
        send_notification_method = getattr(transport_class, 'send_notification')

        #Get the template for sending this event type using this transport
        try:
            template_config = NotificationTemplateConfig.objects.filter(transport=transport, event_type=event.type)
            if len(template_config) == 0:
                template_config = None
            elif not transport.allows_context:
                template_config = template_config[0]
        except:
            continue

        #For every attendant, obtain the subscription for current transport and send the notification
        for attendant in attendants.items():
            attendant = attendant[1]
            try:
                subscription = Subscription.objects.get(transport=transport, user=attendant.user)
                delta = eval(subscription.frequency.delta)
            except:
                subscription = None
                delta = 0

            if subscription is None or subscription.user_is_subscribed(event.type):
                delay = subscription and delta != 0 and transport.allows_freq_config
                send_notification_method(attendant.user, attendant.role, event, template_config, delay)

        if template_config and not get_attendants_methods:
            send_notification_method(None, None, event, template_config)



@task(name='notifications.send_delayed')
def send_delayed_notifications():
    from datetime import timedelta #DO NOT REMOVE!!!
    from .models import Transport, Notification, MultipleNotificationTemplateConfig, Subscription

    transports = Transport.objects.filter(allows_freq_config=True)
    users = User.objects.annotate(count_notifications=Count('notifications')).filter(count_notifications__gt=0)

    for transport in transports:
        for user in users:
            try:
                subscription = Subscription.objects.get(user=user, transport=transport)
                delta = eval(subscription.frequency.delta)
            except:
                subscription = None
                delta = 0

            if not subscription or (subscription.last_sent <= timezone.now() - delta):
                template_config = MultipleNotificationTemplateConfig.objects.get(transport=transport)
                transport_class = import_by_path(transport.cls)
                send_notification_method = getattr(transport_class, 'send_multiple_notification')
                user_notifications = Notification.objects.filter(user=user, transport=transport, sent=False)
                send_notification_method(user, user_notifications, template_config, transport.delete_sent)

                if subscription:
                    subscription.last_sent = timezone.now()
                    subscription.save()

