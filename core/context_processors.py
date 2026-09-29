from django.conf import settings

from .i18n import DEFAULT_LANG, JS_KEYS, translate


def ui(request):
    lang = getattr(request, "ui_lang", DEFAULT_LANG)
    return {
        "LANG": lang,
        "DIR": "rtl" if lang == "ar" else "ltr",
        "OTHER_LANG": "en" if lang == "ar" else "ar",
        "SITE_NAME": settings.SITE_NAME,
        "JS_I18N": {key: translate(key, lang) for key in JS_KEYS},
    }
