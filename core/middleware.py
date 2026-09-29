from django.utils import translation

from .i18n import DEFAULT_LANG, SUPPORTED

COOKIE_NAME = "ui_lang"


class UILanguageMiddleware:
    """Picks the UI language ('ar' | 'en') from a cookie.

    * request.ui_lang  → used by the project's own dictionary ({% t %} tag)
    * translation.activate() → Django's built-in messages (form errors, validators)
      are shown in the same language.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.COOKIES.get(COOKIE_NAME, DEFAULT_LANG)
        if lang not in SUPPORTED:
            lang = DEFAULT_LANG
        request.ui_lang = lang
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", lang)
        return response
