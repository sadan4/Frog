# main.py
#
# Copyright 2021-2023 Andrey Maksimov
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Except as contained in this notice, the name(s) of the above copyright
# holders shall not be used in advertising or otherwise to promote the sale,
# use or other dealings in this Software without prior written
# authorization.

import datetime
import sys
from gettext import gettext as _

import nanoid
from gi.repository import Gtk, Gio, GLib, Notify, Adw, GdkPixbuf, Gdk, GObject
from loguru import logger

from frog.config import RESOURCE_PREFIX, APP_ID
from frog.language_manager import language_manager
from frog.services.clipboard_service import clipboard_service
from frog.services.screenshot_service import ScreenshotService
from frog.services.telemetry import telemetry
from frog.settings import Settings
from frog.window import FrogWindow


class FrogApplication(Adw.Application):
    __gtype_name__ = 'FrogApplication'
    gtk_settings: Gtk.Settings

    settings: Settings = GObject.Property(type=GObject.TYPE_PYOBJECT)
    installation_id: str = GObject.Property(type=str)

    def __init__(self, version=None):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.backend = None
        self.version = version

        # Init GSettings
        self.settings = Settings.new()

        telemetry.set_is_active(self.settings.get_boolean('telemetry'))
        self.ensure_installation_id()

        self.add_main_option(
            'extract_to_clipboard',
            ord('e'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Extract directly into the clipboard"),
            None
        )

        # Initialize tesseract data files storage.
        language_manager.init_tessdata()

        # Initialize libnotify.
        Notify.init("Frog")

    def do_startup(self, *args, **kwargs):
        Adw.Application.do_startup(self)

        # create command line option entries
        shortcut_entry = GLib.OptionEntry()
        shortcut_entry.long_name = 'extract_to_clipboard'
        shortcut_entry.short_name = ord('e')
        shortcut_entry.flags = 0
        shortcut_entry.arg = GLib.OptionArg.NONE
        shortcut_entry.arg_date = None
        shortcut_entry.description = _("Extract directly into the clipboard")
        shortcut_entry.arg_description = None

        self.backend = ScreenshotService()
        self.backend.connect('decoded', FrogApplication.on_decoded)

        action = Gio.SimpleAction.new("show_uri", GLib.VariantType.new('s'))
        action.connect("activate", self.on_show_uri)
        self.add_action(action)

        self.create_action('get_screenshot', self.get_screenshot, ['<primary>g'])
        self.create_action('get_screenshot_and_copy', self.get_screenshot_and_copy, ['<primary><shift>g'])
        self.create_action('copy_to_clipboard', self.on_copy_to_clipboard, ['<primary>g'])
        self.create_action('open_image', self.open_image, ['<primary>o'])
        self.create_action('paste_from_clipboard', self.on_paste_from_clipboard, ['<primary>v'])
        self.create_action('listen', self.on_listen, ['<primary>l'])
        self.create_action('listen_cancel', self.on_listen_cancel, ['<primary><ctrl>l'])
        self.create_action('shortcuts', self.on_shortcuts, ['<primary>question'])

        self.create_action('quit', lambda *_: self.quit(), ['<primary>q', '<primary>w'])
        self.create_action('about', self.on_about)
        self.create_action('preferences', self.on_preferences, ['<primary>comma'])
        self.create_action('github_star', self.on_github_star)

        self.settings.connect("changed", self.on_settings_changed)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = FrogWindow(application=self)
        win.present()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        options = options.end().unpack()

        if "extract_to_clipboard" in options:
            self.backend.capture(self.settings.get_string("active-language"), True)
            return 1

        self.activate()
        return 0

    def ensure_installation_id(self):
        self.installation_id = self.settings.get_string("installation-id")
        if not self.installation_id:
            logger.info("No installation id was found. Generating a new one.")
            self.installation_id = nanoid.generate()
            self.settings.set_string("installation-id", self.installation_id)
            telemetry.set_installation_id(self.installation_id)
            telemetry.capture('new Installation ID generated')

        telemetry.set_installation_id(self.installation_id)

    def on_settings_changed(self, settings, key):
        logger.debug('SETTINGS: %s changed', key)
        if key == "telemetry":
            value = settings.get_boolean(key)
            if value:
                telemetry.capture('telemetry activated')
            else:
                telemetry.capture('telemetry deactivated')
            telemetry.set_is_active(value)

    def on_preferences(self, _action, _param) -> None:
        telemetry.capture('preferences activated')
        self.get_active_window().show_preferences()

    def on_github_star(self, _action, _param) -> None:
        telemetry.capture('star github activated')
        launcher: Gtk.UriLauncher = Gtk.UriLauncher()
        launcher.set_uri('https://github.com/TenderOwl/Frog')
        launcher.launch(callback=self._on_github_star)

    def on_about(self, _action, _param):
        telemetry.capture('about activated')
        about_window = Adw.AboutDialog(
            application_name="Frog",
            application_icon=APP_ID,
            version=self.version,
            copyright=f'© {datetime.date.today().year} Tender Owl',
            website="https://getfrog.app",
            issue_url="https://github.com/TenderOwl/Frog/issues/new",
            license_type=Gtk.License.MIT_X11,
            developer_name="TenderOwl Team",
            developers=["Andrey Maksimov"],
            release_notes="""<p>In this update, we've made a number of improvements to our app.</p>
                <ul>
                    <li>New look and feel for language selection popover.</li>
                    <li>Now Frog deletes only its temporary files.</li>
                    <li>Temporarily disabled Text-to-Speech until we find a better "offline" solution.</li>
                    <li>We decided to collect anonymous usage data. You can disable it in the preferences.</li>
                    <li>Updated translations.</li>
                </ul>
                <p>Full list of changes you may find in the repository.</p>
                <p>We hope you enjoy our work!</p>
            """
        )
        about_window.present(self.props.active_window)

    def on_shortcuts(self, _action, _param):
        telemetry.capture('shortcuts activated')
        builder = Gtk.Builder()
        builder.add_from_resource(f"{RESOURCE_PREFIX}/ui/shortcuts.ui")
        builder.get_object("shortcuts").set_transient_for(self.get_active_window())
        builder.get_object("shortcuts").present()

    def on_copy_to_clipboard(self, _action, _param) -> None:
        telemetry.capture('copy_to_clipboard activated')
        self.get_active_window().on_copy_to_clipboard(self)

    def on_show_uri(self, _action, param) -> None:
        telemetry.capture('show_uri activated')
        Gtk.show_uri(None, param.get_string(), Gdk.CURRENT_TIME)

    def get_screenshot(self, _action, _param) -> None:
        telemetry.capture('screenshot activated')
        self.get_active_window().get_screenshot()

    def get_screenshot_and_copy(self, _action, _param) -> None:
        telemetry.capture('screenshot_and_copy activated')
        self.get_active_window().get_screenshot(copy=True)

    def open_image(self, _action, _param) -> None:
        telemetry.capture('open_image activated')
        self.get_active_window().open_image()

    def on_paste_from_clipboard(self, _action, _param) -> None:
        telemetry.capture('paste_from_clipboard activated')
        self.get_active_window().on_paste_from_clipboard(self)

    @staticmethod
    def on_decoded(_sender, text: str, copy: bool) -> None:
        # icon = GdkPixbuf.Pixbuf.new_from_resource_at_scale(
        #     f"{RESOURCE_PREFIX}/icons/com.github.tenderowl.frog.svg",
        #     128, 128, True
        # )

        if not text:
            # notification: Notify.Notification = Notify.Notification.new(
            #     summary='Frog',
            #     body=_("No text found. Try to grab another region.")
            # )
            # notification.set_icon_from_pixbuf(icon)
            # notification.show()
            pass
        if copy:
            clipboard_service.set(text)
        else:
            logger.debug(f'{text}\n')

    def on_listen(self, _sender, _event):
        self.get_active_window().on_listen()

    def on_listen_cancel(self, _sender, _event):
        self.get_active_window().on_listen_cancel()

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def _on_github_star(self, _, result):
        pass


def main(version):
    app = FrogApplication(version)
    return app.run(sys.argv)
