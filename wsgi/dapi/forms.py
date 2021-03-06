from django.forms import *
from dapi.models import MetaDap, Dap, Report, Profile
from django.contrib.auth.models import User
from captcha.fields import CaptchaField
from social.apps.django_app.default import models as social_models


VERIFY_HELP_TEXT = 'Enter the {what} of this dap to verify the {why}.'


class UploadDapForm(Form):
    file = FileField()


class UserForm(ModelForm):

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        if self.instance.profile.syncs.exists():
            self.fields['email'].help_text = 'Further fields cannot be edited, because at least one service is configured to override those data on login. See below to disable it.'
            for field in 'email first_name last_name'.split():
                self.fields[field].widget.attrs['readonly'] = 'readonly'
                self.fields[field].widget.attrs['class'] = 'disabled'


class ProfileSyncForm(ModelForm):

    class Meta:
        model = Profile
        fields = ('syncs',)
        help_texts = {
            'syncs': 'Select services, that will override your name and e-mail on login.',
        }

    def __init__(self, *args, **kwargs):
        social_models.UserSocialAuth.__str__ = lambda self: self.get_backend().name
        super(ModelForm, self).__init__(*args, **kwargs)
        self.fields['syncs'].queryset = social_models.UserSocialAuth.objects.filter(user=self.instance.user)


class ComaintainersForm(ModelForm):

    class Meta:
        model = MetaDap
        fields = ('comaintainers',)

    def __init__(self, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        self.fields['comaintainers'].help_text = ''
        self.fields['comaintainers'].queryset = User.objects.exclude(id=self.instance.user_id)


class DeleteDapForm(Form):
    verification = CharField(max_length=200, help_text=VERIFY_HELP_TEXT.format(what='name', why='deletion'))


class DeleteUserForm(Form):
    verification = CharField(max_length=30, help_text='Enter the username to confirm the deletion.')


class DeleteVersionForm(Form):
    verification_name = CharField(max_length=200, help_text=VERIFY_HELP_TEXT.format(what='name', why='deletion'))
    verification_version = CharField(max_length=200, help_text=VERIFY_HELP_TEXT.format(what='version', why='deletion'))


class ActivationDapForm(ModelForm):
    verification = CharField(max_length=200, help_text=VERIFY_HELP_TEXT.format(what='name', why='deactivation'))

    class Meta:
        model = MetaDap
        fields = ('active',)


class TransferDapForm(ModelForm):
    verification = CharField(max_length=200, help_text='Type the name of this dap to verify the transfer.')

    class Meta:
        model = MetaDap
        fields = ('user',)


class LeaveDapForm(Form):
    verification = CharField(max_length=200, help_text='Type the name of this dap to verify the leaving.')


class TagsForm(ModelForm):

    class Meta:
        model = MetaDap
        fields = ('tags',)


class ReportForm(ModelForm):

    class Meta:
        model = Report
        fields = ('problem', 'versions', 'message')
        help_texts = {
            'problem': 'Select the type of problem you want to report.',
            'versions': 'Where this problem occurs? If you are not sure, you can leave it blank.',
            'message': 'Describe the problem you want to report.',
        }

    def __init__(self, metadap, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        self.instance.metadap = metadap
        self.fields['versions'].queryset = Dap.objects.filter(metadap=metadap)


class ReportAnonymousForm(ReportForm):
    captcha = CaptchaField()

    class Meta(ReportForm.Meta):
        fields = ReportForm.Meta.fields + ('email',)
        help_texts = ReportForm.Meta.help_texts
        help_texts['email'] = 'Optional. So we can inform you about the solution. We don\'t send spam or sell e-mail addresses.'
