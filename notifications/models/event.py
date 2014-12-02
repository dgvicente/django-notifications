# coding=utf-8
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.managers import CurrentSiteManager
from django.contrib.sites.models import Site
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.db import models
from .action import Action
from ..fields import JSONField


class EventTypeCategory(models.Model):
    name = models.CharField(max_length=255)
    read_as = models.CharField(max_length=255)

    class Meta:
        app_label = 'notifications'

    def __unicode__(self):
        return self.read_as or self.name


class EventObjectRole(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        app_label = 'notifications'

    def __unicode__(self):
        return self.name


class EventType(models.Model):
    name = models.CharField(max_length=255)
    read_as = models.CharField(max_length=255)
    action = models.ForeignKey(Action)
    target_type = models.CharField(max_length=255)
    category = models.ForeignKey(EventTypeCategory, null=True)
    immediate = models.BooleanField(default=False)

    class Meta:
        app_label = 'notifications'

    def __unicode__(self):
        return self.read_as or self.name


class Event(models.Model):
    type = models.ForeignKey(EventType)
    user = models.ForeignKey(User, related_name='events')
    date = models.DateTimeField(auto_now_add=True)

    target_type = models.ForeignKey(ContentType, verbose_name=_('target type'), related_name="%(class)s")
    target_pk = models.TextField(_('target ID'))
    target_object = GenericForeignKey(ct_field="target_type", fk_field="target_pk")

    extra_data = JSONField(null=True, blank=True)
    details = models.TextField(max_length=500)

    site = models.ForeignKey(Site, null=True)

    objects = models.Manager()
    on_site = CurrentSiteManager()

    class Meta:
        app_label = 'notifications'

    def __unicode__(self):
        return self.details

    def get_related_obj_by_role_name(self, role_name):
        try:
            role = EventObjectRole.objects.get(name=role_name)
            related_objects = self.eventobjectrolerelation_set.filter(role=role)
            if len(related_objects):
                return related_objects[0].target_object
            return None
        except:
            return None


@receiver(pre_save, sender=Event, dispatch_uid='pre_save_event')
def pre_save_handler(instance, **kwargs):
    if not instance.pk and not instance.site_id:
        instance.site_id = getattr(instance.target_object, 'site_id', Site.objects.get_current().pk)


class EventObjectRoleRelation(models.Model):
    event = models.ForeignKey(Event)
    role = models.ForeignKey(EventObjectRole)

    target_type = models.ForeignKey(ContentType, verbose_name=_('target type'), related_name="%(class)s")
    target_pk = models.TextField(_('target ID'))
    target_object = GenericForeignKey(ct_field="target_type", fk_field="target_pk")

    class Meta:
        app_label = 'notifications'

    def __unicode__(self):
        return self.target_object

