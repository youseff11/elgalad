from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from django.utils.translation import get_language

from .i18n import translate
from .models import AIConfig

User = get_user_model()


class StyledMixin:
    """Adds the design-system CSS class to every widget."""

    def _style(self):
        for name, field in self.fields.items():
            css = "input"
            if isinstance(field.widget, forms.CheckboxInput):
                css = "checkbox"
            elif isinstance(field.widget, forms.Select):
                css = "input select"
            field.widget.attrs.setdefault("class", css)
            field.widget.attrs.setdefault("id", f"id_{name}")


class LoginForm(StyledMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})


class RegisterForm(StyledMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        for f in self.fields.values():
            f.help_text = ""

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(translate("err_email_taken", (get_language() or "ar")[:2]))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        if commit:
            user.save()
        return user


class ProfileForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class StyledPasswordChangeForm(StyledMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        for f in self.fields.values():
            f.help_text = ""


class AIConfigForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = AIConfig
        fields = (
            "base_url",
            "timeout",
            "default_max_length",
            "default_min_length",
            "default_num_beams",
            "default_length_penalty",
            "default_repetition_penalty",
            "default_no_repeat_ngram_size",
        )
        widgets = {
            "base_url": forms.URLInput(attrs={"placeholder": "https://xxxx.trycloudflare.com", "dir": "ltr"}),
            "default_length_penalty": forms.NumberInput(attrs={"step": "0.1", "min": "0.1", "max": "3"}),
            "default_repetition_penalty": forms.NumberInput(attrs={"step": "0.1", "min": "1", "max": "2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        limits = {
            "timeout": (5, 600),
            "default_max_length": (16, 512),
            "default_min_length": (5, 128),
            "default_num_beams": (1, 8),
            "default_no_repeat_ngram_size": (0, 5),
        }
        for name, (lo, hi) in limits.items():
            self.fields[name].widget.attrs.update({"min": lo, "max": hi})
        self._int_limits = limits

    def clean_base_url(self):
        return (self.cleaned_data.get("base_url") or "").strip().rstrip("/")

    def clean(self):
        data = super().clean()
        for name, (lo, hi) in self._int_limits.items():
            val = data.get(name)
            if val is not None and not (lo <= val <= hi):
                self.add_error(name, f"{lo} – {hi}")
        lp = data.get("default_length_penalty")
        rp = data.get("default_repetition_penalty")
        if lp is not None and not (0.1 <= lp <= 3):
            self.add_error("default_length_penalty", "0.1 – 3.0")
        if rp is not None and not (1 <= rp <= 2):
            self.add_error("default_repetition_penalty", "1.0 – 2.0")
        mx, mn = data.get("default_max_length"), data.get("default_min_length")
        if mx and mn and mn >= mx:
            self.add_error("default_min_length", "min < max")
        return data
