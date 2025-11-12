from loader import _

"""
Text moved to separate file for easy editing
"""


class MessageText:
    # Welcome and information
    @property
    def WELCOME(self):
        return _("""
Hey! 👋

Welcome to Michi dating bot! 💕
To get started, create your profile — it's quick and easy.

Wishing you great connections and exciting meetings!
""")

    @property
    def INFO(self):
        return _("""
👋
A bit about the bot:
This bot was inspired by popular dating bots.
All code is open source and available on <a href='https://github.com/devvsima/dating-bot'>GitHub</a>

For questions and suggestions, contact: @devvsima.
""")

    # UPDATED: Main menu with Enter Mode option
    @property
    def MENU(self):
        return _("""
👤 My profile
✉️ Invite friends
🎭 Enter Mode
""")

    # NEW: Mode selection prompt
    @property
    def SELECT_MODE(self):
        return _("""
🎭 <b>Which mode do you want to enter?</b>

Choose your vibe:
""")

    # NEW: Mode-specific menus
    @property
    def MODE_FUN_MENU(self):
        return _("""
<b>Pick your next move, darling:</b>

🔍 - Hunt for matches in Fun mode
📭 - See who crushed on you in Fun mode
💤 - Return to main menu
""")

    @property
    def MODE_DATES_MENU(self):
        return _("""
<b>What would you like to do?</b>

🔍 - Browse profiles in Dating mode
📭 - See who liked you in Dating mode
💤 - Return to main menu
""")

    @property
    def MODE_FRIENDS_MENU(self):
        return _("""
<b>What would you like to do?</b>

🔍 - Browse profiles in Friends mode
📭 - See who liked you in Friends mode
💤 - Return to main menu
""")

    @property
    def PROFILE_MENU(self):
        return _("""
🔄 Recreate profile
🖼 Change photo
✍️ Change description
❌ Disable profile

↩️ Back
""")

    @property
    def UNKNOWN_COMMAND(self):
        return _("Unknown command. If you're lost, type /start.")

    # Mood mode messages
    @property
    def MODE_FUN_ACTIVATED(self):
        return _("""
🍆👅🍑💦 <b>Fun Mode Activated!</b>

You're now browsing profiles of people looking for casual fun (Hookups) and exciting meetups. Ready to see who's down for you today?
""")

    @property
    def MODE_DATES_ACTIVATED(self):
        return _("""
❤️🥂 <b>Dates Mode Activated!</b>

You're now browsing profiles of people looking for meaningful romantic connections. Let's find your match!
""")

    @property
    def MODE_FRIENDS_ACTIVATED(self):
        return _("""
🤝 <b>Friends Mode Activated!</b>

You're now browsing profiles of people looking for genuine friendships and connections. Let's build your circle!
""")

    def MODE_SWITCH_CONFIRM(self, current_mode: str, new_mode: str):
        mode_icons = {'fun': '🍆👅🍑💦', 'dates': '❤️🥂', 'friends': '🤝'}
        mode_names = {'fun': 'Fun', 'dates': 'Dates', 'friends': 'Friends'}
        
        return _("""
{new_icon} <b>Switch to {new_name} Mode?</b>

You're currently in {current_name} mode. Switching to {new_name} will show you people looking for {new_description} instead.

Do you want to leave {current_name} mode and enter {new_name} mode?
""").format(
            new_icon=mode_icons.get(new_mode, ''),
            new_name=mode_names.get(new_mode, ''),
            current_name=mode_names.get(current_mode, ''),
            new_description=new_mode
        )

    @property
    def MODE_SWITCH_CANCELLED(self):
        return _("Okay, staying in current mode! 👍")

    # Profile creation and editing - UPDATED FOR ROLES
    @property
    def ROLE(self):
        return _("What's your role? 👤")

    @property
    def FIND_ROLE(self):
        return _("Who are you looking for? 💕")

    @property
    def PHOTO(self):
        return _("Upload your photo! You can send up to 3 photos at once 📸")

    @property
    def NAME(self):
        return _("What's your name? ✍️")

    @property
    def AGE(self):
        return _("How old are you? 🎂")

    @property
    def CITY(self):
        return _("What's your city? 🏙️")

    @property
    def DESCRIPTION(self):
        return _("Tell us a bit about yourself — this helps others get to know you better! 📝")

    # NEW: Hosting question
    @property
    def HOSTING(self):
        return _("Can you host? 🏠")

    # NEW: Hosting filter prompt
    @property
    def HOSTING_FILTER(self):
        return _("""
<b>Looking for people who?</b>
""")

    @property
    def PROFILE_CREATED(self):
        return _("Great! Your profile is ready — now you can start finding interesting people 💬")

    @property
    def DISABLE_PROFILE(self):
        return _("""
❌ Your profile is disabled, some features are now unavailable.
💬 To reactivate your profile, send /start.""")

    @property
    def ACTIVATE_PROFILE_ALERT(self):
        return _("✅ Your profile has been successfully restored! You can use the bot again.")

    @property
    def SEARCH(self):
        return _("🔍 Searching...")

    @property
    def ARCHIVE_SEARCH(self):
        return _("{} people liked your profile! Let's see who they are:")

    # UPDATED: Mode-specific empty search messages
    @property
    def INVALID_PROFILE_SEARCH(self):
        return _("No suitable profiles found in this mode. Try choosing a different city. 🌍")

    def EMPTY_PROFILE_SEARCH(self, mode: str = None):
        if mode == 'fun':
            return _("No more profiles in Fun mode. Try again later! 🎉")
        elif mode == 'dates':
            return _("No more profiles in Dating mode. Try again later! 💕")
        elif mode == 'friends':
            return _("No more profiles in Friends mode. Try again later! 👥")
        return _("No more profiles. Try again later! 😊")

    def LIKE_PROFILE(self, language: str):
        return _(
            "Your profile got <b>{}</b> ❤️\n\n📭 Click to see",
            locale=language,
        )

    # UPDATED: Mode-specific empty inbox messages
    def LIKE_ARCHIVE(self, mode: str = None):
        if mode == 'fun':
            return _("No one has liked you in Fun mode yet, but there's still time! 🎉")
        elif mode == 'dates':
            return _("No one has liked you in Dating mode yet, but there's still time! 💕")
        elif mode == 'friends':
            return _("No one has liked you in Friends mode yet, but there's still time! 👥")
        return _("No one has liked you yet, but there's still time!")

    def LIKE_ACCEPT(self, language: str):
        return _(
            "Hope you have a great time ;) <a href='{}'>{}</a>",
            locale=language,
        )

    @property
    def MESSAGE_TO_YOU(self):
        return _("Message for you:\n{}")

    @property
    def MAILING_TO_USER(self):
        return _(
            "You can write a message to the user, up to 250 characters. ✉️\n\nIf you don't want to write, click the button below."
        )

    @property
    def MAILING_LIKE(self):
        return _("Message sent, waiting for response.")

    @property
    def INVALID_MAILING_TO_USER(self):
        return _("Invalid message. Please write up to 250 characters.")

    @property
    def CANNCELED_LETTER(self):
        return _("Okay, won't send anything.")

    # Errors and validation
    @property
    def INVALID_RESPONSE(self):
        return _("Invalid response. Please choose from the keyboard or write correctly. 📝")

    @property
    def INVALID_LONG_RESPONSE(self):
        return _("Character limit exceeded. Please shorten your message. ✂️")

    @property
    def INVALID_CITY_RESPONSE(self):
        return _("City not found :(")

    @property
    def INVALID_PHOTO(self):
        return _(
            "Invalid photo format! Please upload an image in the correct format. 🖼️"
        )

    @property
    def INVALID_AGE(self):
        return _("Invalid format, age must be entered as numbers. 🔢")

    @property
    def INVITE_FRIENDS(self):
        return _(
            "Invite friends and get bonuses!\n\nInvited users: <b>{}</b>\n\nFriend link:\n<code>{}</code>"
        )

    @property
    def CHANNEL(self):
        return _("Our channel:\n{}")

    # Language
    @property
    def CHANGE_LANG(self):
        return _("Choose the bot language you want to switch to: 🌐")

    def DONE_CHANGE_LANG(self, language: str):
        return _("Bot language changed! ✅", locale=language)

    # Complaints and moderation
    @property
    def COMPLAINT(self):
        return _("""
Select complaint reason:
🔞 Inappropriate content
💰 Advertising
🔫 Other

↩️ Back
""")

    @property
    def REPORT_TO_USER(self):
        return """
User <code>{}</code> (@{}) sent a complaint
about a user profile: <code>{}</code> (@{})

The reason: {}
"""

    @property
    def REPORT_TO_PROFILE(self):
        return _("✅ Complaint successfully submitted for review!")

    # Photo editing
    @property
    def PHOTO_EDIT_START(self):
        return _("Upload new photos! You can send up to 3 photos 📸")

    @property
    def PHOTO_UNCHANGED(self):
        return _("Photos unchanged")

    @property
    def PHOTO_NO_UPLOADED(self):
        return _("You didn't upload any photos. Try again.")

    @property
    def PHOTO_SAVE_ERROR(self):
        return _("❌ Error saving photo. Try again.")

    @property
    def PHOTO_SAVE_FINISH_BUTTON(self):
        return _("That's all, save photos")

    @property
    def PHOTO_PROGRESS_TEMPLATE(self):
        return _(
            "📸 Photo {current}/{total} uploaded!\n\nYou can upload {remaining} more photos or click '{finish_button}'"
        )

    def PHOTO_PROGRESS(self, current: int, total: int = 3):
        remaining = total - current
        finish_button_text = _("That's all, save photos")
        return self.PHOTO_PROGRESS_TEMPLATE.format(
            current=current, total=total, remaining=remaining, finish_button=finish_button_text
        )

    def PHOTO_SAVED(self, count: int):
        return _("Saved {} photos!").format(count)

    def PHOTO_ALL_UPLOADED(self, count: int = 3):
        return _("All {} photos uploaded!").format(count)

    @property
    def PHOTO_LIMIT_REACHED(self):
        return _("❌ Maximum 3 photos! Click 'That's all, save photos' to save.")

    @property
    def PHOTO_UPLOAD_INSTRUCTION(self):
        return _("📸 Send a photo or choose an action from the menu")

    @property
    def PHOTO_REQUIRED_FOR_PROFILE(self):
        return _("❌ You need to upload at least one photo to create a profile!")


message_text = MessageText()