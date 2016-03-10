import lxml.html
import premailer

import django.contrib.auth

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader, Context

try:
    from django.template.engine import Engine
except ImportError:
    Engine = None
    from django.template.context import get_standard_processors


class TemplateEmail(EmailMultiAlternatives):
    """
    Makes it a little easier to send HTML+plaintxt emails using templates
    """
    template = None
    template_override = None # allow template to be overwritten
    context = {}
    html = None

    _rendered = False

    def __init__(self, *args, **kwargs):
        context = kwargs.pop('context', self.context)
        template = kwargs.pop('template', self.template)
        template_override = kwargs.pop('template_override', self.template_override)
        super(TemplateEmail, self).__init__(*args, **kwargs)
        self.template = template
        self.template_override = template_override

        self._default_context = {}
        self._override_context = context or {}

    def render(self):
        if self.template_override:
            tpl = self.template_override
        else:
            tpl = loader.get_template(self.template)

        context = self._default_context
        if getattr(settings, "TEMPLATE_EMAIL_USE_CONTEXT_PROCESSORS", False):
            if Engine:
                standard_processors = Engine.get_default().template_context_processors
            else:
                standard_processors = get_standard_processors()

            for processor in standard_processors:
                try:
                    context.update(processor(None))
                except:
                    pass

        context.update(self.context)
        context.update(self._override_context)

        context_subject = dict(context, _subject=True)
        context_body = dict(context, _body=True)
        context_html = dict(context, _bodyhtml=True)

        subject = tpl.render(Context(context_subject)).strip()
        body = tpl.render(Context(context_body)).strip()
        html = tpl.render(Context(context_html)).strip()

        if subject != '':
            self.subject = subject
        if body != '':
            self.body = body
        if html != '':
            html_doc = None
            base_url = getattr(settings, "TEMPLATE_EMAIL_BASE_URL", None)
            if base_url:
                html_doc = html_doc or lxml.html.fromstring(html)
                html_doc.make_links_absolute(base_url)
            if getattr(settings, "TEMPLATE_EMAIL_INLINE_CSS", False):
                html_doc = html_doc or lxml.html.fromstring(html)
                opts = getattr(
                    settings, "TEMPLATE_EMAIL_INLINE_CSS_OPTIONS", {})
                html_doc = premailer.Premailer(html_doc, **opts).transform()
            if html_doc:
                html = lxml.html.tostring(
                    html_doc, include_meta_content_type=True).decode('utf-8')
            self.html = html

        self._rendered = True

    def send(self, *args, **kwargs):
        if not self._rendered:
            self.render()

        if self.html and self.html != '':
            self.attach_alternative(content=self.html, mimetype='text/html')

        if not isinstance(self.to, (list, tuple)):
            self.to = [self.to]

        for i, recip in enumerate(self.to):
            # Convert user objects if they're in the recipients list
            try:
                AbstractBaseUser = django.contrib.auth.base_user.AbstractBaseUser
            except ImportError:
                AbstractBaseUser = django.contrib.auth.models.AbstractBaseUser

            if isinstance(recip, AbstractBaseUser):
                self.to[i] = '"%s" <%s>' % (recip.get_full_name(), recip.email)

        super(TemplateEmail, self).send(*args, **kwargs)
