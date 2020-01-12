import aiotask_context as context
import aiohttp_i18n.i18n

import settings


# noinspection PyProtectedMember
# TODO: escape from using `aiohttp_i18n.i18n`
class AioHttpGettextTranslations(aiohttp_i18n.i18n._GettextTranslations):
    """ This singleton extends logic for jinja2 i18n support of _GettextTranslations """

    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(AioHttpGettextTranslations, cls).__new__(cls)

        return cls.__instance

    def __init__(self):
        super().__init__()
        self.set_default_locale(settings.LOCALES_BY_DEFAULT)
        self.load_translations(settings.LOCALES_PATH, "messages")

    @property
    def current_language(self):
        """
        Aiohttp context can contain both language as string (from cookies) or
        language as Locale obj (from user's headers)
        """
        try:
            current_locale = context.get("locale")
        except ValueError:
            current_locale = settings.LOCALES_BY_DEFAULT

        if isinstance(current_locale, str):
            lang = current_locale
        else:
            lang = (
                current_locale.language
                if current_locale
                else settings.LOCALES_BY_DEFAULT
            )

        if lang not in settings.LOCALES:
            lang = settings.LOCALES_BY_DEFAULT

        return lang

    def gettext(self, message):
        """ Required method for getting translate (to current language) """
        return self.translations[self.current_language].gettext(message)

    def ngettext(self, singular, plural, n):
        """ Required method for getting translate in plural (to current language) """
        return self.translations[self.current_language].ngettext(singular, plural, n)


aiohttp_translations = AioHttpGettextTranslations()
