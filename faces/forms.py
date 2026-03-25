from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Event, Photo

MAX_BULK_UPLOAD_FILES = 20


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        self.max_files = kwargs.pop("max_files", None)
        widget = kwargs.pop("widget", MultipleFileInput())
        if self.max_files is not None:
            widget.attrs["data-upload-batch-size"] = str(self.max_files)
        kwargs["widget"] = widget
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            files = [single_file_clean(item, initial) for item in data]
        else:
            files = [single_file_clean(data, initial)]
        return files


class PhotoUploadForm(forms.ModelForm):
    captured_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = Photo
        fields = ["title", "event_name", "captured_at", "original_image"]


class EventCreateForm(forms.ModelForm):
    event_date = forms.DateField(required=True, widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Event
        fields = ["name", "event_date"]


class BulkPhotoUploadForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.none())
    photos = MultipleFileField(max_files=MAX_BULK_UPLOAD_FILES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = Event.objects.order_by("-created_at")


class EventPhotoUploadForm(forms.Form):
    photos = MultipleFileField(max_files=MAX_BULK_UPLOAD_FILES)


class FaceSearchForm(forms.Form):
    username = forms.CharField(max_length=150)
    query_image = forms.ImageField()


class StudioAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput())


class StudioRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email")
