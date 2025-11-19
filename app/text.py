from loader import _

"""
Text moved to separate file for easy editing
"""


class MessageText:
    # Welcome and information
    @property
    def WELCOME(self):
        return _("""
Hey there! 👋🌈

Welcome to <b>CONQUEER</b> — where queer kings conquer connections! 💪✨

Whether you're ready to:
🍆👅🍑💦 <b>Fun Mode</b> — Casual hookups and wild nights
❤️🥂 <b>Dating Mode</b> — Find your king or prince
🤝 <b>Friends Mode</b> — Build your chosen family

Your kingdom awaits! Create your profile and start conquering.

<i>Be bold. Be proud. Be you.</i> 🏳️‍🌈
""")

    @property
    def INFO(self):
        return _("""
🌈 <b>About CONQUEER</b>

Your platform to conquer the dating scene — built by queer men, for queer men.

<b>Three Modes. Infinite Possibilities:</b>
🍆👅🍑💦 <b>Fun Mode</b> — No strings, just vibes
❤️🥂 <b>Dating Mode</b> — Find something real
🤝 <b>Friends Mode</b> — Your queer tribe

<b>Conquer On Your Terms:</b>
- Choose your role: Top, Bottom, or Verse
- Filter by age range and hosting
- Location-based matching
- Safe, private, and judgment-free

<b>Open Source & Community-Driven</b>
Built with love on <a href='https://github.com/0xkiawa/dating-bot'>GitHub</a>

Questions or feedback? Hit up: @devvsima

Now go forth and conquer! 👑
""")

    # UPDATED: Main menu with Enter Mode option
    @property
    def MENU(self):
        return _("""
<b>CONQUEER Command Center</b> 👑

👤 My Profile — Own your presence
✉️ Invite Friends — Expand the kingdom
🎭 Enter Mode — Start conquering
""")

    # NEW: Mode selection prompt
    @property
    def SELECT_MODE(self):
        return _("""
🎭 <b>Choose Your Conquest</b>

What are you hunting for today?

Pick your mode and start browsing:
""")

    # NEW: Mode-specific menus
    @property
    def MODE_FUN_MENU(self):
        return _("""
🍆👅🍑💦 <b>Fun Mode Active</b>

Ready to play?

🔍 - Browse hot matches
📭 - See who wants you
🎂 - Set age range
🏠 - Set hosting preference
💤 - Return to main menu
""")

    @property
    def MODE_DATES_MENU(self):
        return _("""
❤️🥂 <b>Dating Mode Active</b>

Looking for something real?

🔍 - Browse potential matches
📭 - See who's interested
🎂 - Set age range
🏠 - Set hosting preference
💤 - Return to main menu
""")

    @property
    def MODE_FRIENDS_MENU(self):
        return _("""
🤝 <b>Friends Mode Active</b>

Building your tribe?

🔍 - Browse friendly faces
📭 - See who reached out
🎂 - Set age range
🏠 - Set hosting preference
💤 - Return to main menu
""")

    @property
    def PROFILE_MENU(self):
        return _("""
<b>Profile Management</b> 👤

🔄 Recreate profile
🖼 Change photo
✍️ Change description
❌ Disable profile

↩️ Back
""")

    @property
    def UNKNOWN_COMMAND(self):
        return _("Unknown command, king. Type /start to get back on track. 👑")

    # Mood mode messages
    @property
    def MODE_FUN_ACTIVATED(self):
        return _("""
🍆👅🍑💦 <b>Fun Mode Activated!</b>

Time to play! You're now browsing guys looking for casual hookups and steamy encounters.

Who's ready for you tonight? Let's find out! 🔥
""")

    @property
    def MODE_DATES_ACTIVATED(self):
        return _("""
❤️🥂 <b>Dating Mode Activated!</b>

Looking for something deeper? You're now browsing guys seeking meaningful connections and romance.

Your match might be one swipe away! 💕
""")

    @property
    def MODE_FRIENDS_ACTIVATED(self):
        return _("""
🤝 <b>Friends Mode Activated!</b>

Building your tribe! You're now browsing guys looking for genuine friendships and community.

Let's expand your chosen family! 🌈
""")

    def MODE_SWITCH_CONFIRM(self, current_mode: str, new_mode: str):
        mode_icons = {'fun': '🍆👅🍑💦', 'dates': '❤️🥂', 'friends': '🤝'}
        mode_names = {'fun': 'Fun', 'dates': 'Dating', 'friends': 'Friends'}
        mode_desc = {
            'fun': 'casual hookups and fun',
            'dates': 'romantic connections',
            'friends': 'platonic friendships'
        }
        
        return _("""
{new_icon} <b>Switch to {new_name} Mode?</b>

You're currently in <b>{current_name} mode</b>. Switching to <b>{new_name} mode</b> will show you guys looking for <b>{new_description}</b> instead.

Ready to make the switch?
""").format(
            new_icon=mode_icons.get(new_mode, ''),
            new_name=mode_names.get(new_mode, ''),
            current_name=mode_names.get(current_mode, ''),
            new_description=mode_desc.get(new_mode, new_mode)
        )

    @property
    def MODE_SWITCH_CANCELLED(self):
        return _("Staying put! Back to your current mode. 👍")

    # Profile creation and editing - UPDATED FOR ROLES
    @property
    def ROLE(self):
        return _("What's your position? 🔥\n\nTop, Bottom, or Verse?")

    @property
    def FIND_ROLE(self):
        return _("Who are you looking for? 💕\n\nTop, Bottom, Verse, or All?")

    @property
    def PHOTO(self):
        return _("Show yourself! 📸\n\nUpload up to 3 photos (make it count!)")

    @property
    def NAME(self):
        return _("What should we call you? ✍️")

    @property
    def AGE(self):
        return _("How old are you, king? 🎂")

    @property
    def CITY(self):
        return _("What city do you reign in? 🏙️")

    @property
    def DESCRIPTION(self):
        return _("Tell us about yourself! 📝\n\nWhat makes you... you? (This is your chance to shine!)")

    # NEW: Hosting question
    @property
    def HOSTING(self):
        return _("Can you host? 🏠\n\n(Important for Fun mode!)")

    # NEW: Hosting filter prompt
    @property
    def HOSTING_FILTER(self):
        return _("""
<b>Hosting Preference?</b> 🏠

Who do you want to see?
""")

    @property
    def PROFILE_CREATED(self):
        return _("👑 <b>Profile created!</b>\n\nYou're all set! Time to start conquering. Hit 🎭 to choose your mode!")

    @property
    def DISABLE_PROFILE(self):
        return _("""
❌ <b>Profile disabled</b>

Your profile is now hidden and some features are unavailable.

Want to come back? Just send /start to reactivate!
""")

    @property
    def ACTIVATE_PROFILE_ALERT(self):
        return _("✅ <b>Welcome back, king!</b>\n\nYour profile is active again. Let's conquer! 👑")

    @property
    def SEARCH(self):
        return _("🔍 <b>Searching for matches...</b>")

    @property
    def ARCHIVE_SEARCH(self):
        return _("📬 <b>{} guys liked your profile!</b>\n\nLet's see who they are:")

    # UPDATED: Mode-specific empty search messages
    @property
    def INVALID_PROFILE_SEARCH(self):
        return _("No matches found in this mode. Try adjusting your filters or check back later! 🌍")

    def EMPTY_PROFILE_SEARCH(self, mode: str = None):
        if mode == 'fun':
            return _("🍆 <b>No more profiles in Fun mode!</b>\n\nTry changing your age/hosting filters or check back later for fresh meat! 🔥")
        elif mode == 'dates':
            return _("❤️ <b>No more profiles in Dating mode!</b>\n\nAdjust your filters or come back soon — your match might be just around the corner! 💕")
        elif mode == 'friends':
            return _("🤝 <b>No more profiles in Friends mode!</b>\n\nTweak your filters or check back later to grow your tribe! 🌈")
        return _("😔 <b>No more profiles right now!</b>\n\nAdjust your filters (age/hosting) or try again later!")

    def LIKE_PROFILE(self, language: str):
        return _(
            "🔥 <b>You got {} likes!</b>\n\n📭 Tap to see who's interested",
            locale=language,
        )

    # UPDATED: Mode-specific empty inbox messages
    def LIKE_ARCHIVE(self, mode: str = None):
        if mode == 'fun':
            return _("🍆 No one's crushed on you in Fun mode yet... but the night is young! 🔥")
        elif mode == 'dates':
            return _("❤️ No one's swiped right in Dating mode yet... but your person is out there! 💕")
        elif mode == 'friends':
            return _("🤝 No friend requests in Friends mode yet... but your tribe is forming! 🌈")
        return _("📭 Your inbox is empty... for now! Keep conquering! 👑")

    def LIKE_ACCEPT(self, language: str):
        return _(
            "🎉 <b>It's a match!</b>\n\nGo conquer together: <a href='{}'>{}</a>",
            locale=language,
        )

    @property
    def MESSAGE_TO_YOU(self):
        return _("💌 <b>Message for you:</b>\n\n{}")

    @property
    def MAILING_TO_USER(self):
        return _(
            "✉️ <b>Send a message</b> (up to 250 characters)\n\nMake it count! Or skip with the button below."
        )

    @property
    def MAILING_LIKE(self):
        return _("✅ Message sent! Now we wait... 🤞")

    @property
    def INVALID_MAILING_TO_USER(self):
        return _("⚠️ Message too long! Keep it under 250 characters.")

    @property
    def CANNCELED_LETTER(self):
        return _("❌ Message cancelled. Moving on!")

    # Errors and validation
    @property
    def INVALID_RESPONSE(self):
        return _("⚠️ Invalid choice. Use the keyboard or type correctly! 📝")

    @property
    def INVALID_LONG_RESPONSE(self):
        return _("⚠️ Too long! Shorten your message. ✂️")

    @property
    def INVALID_CITY_RESPONSE(self):
        return _("🌍 City not found. Try again with a different spelling!")

    @property
    def INVALID_PHOTO(self):
        return _("⚠️ Invalid photo format! Please upload a proper image. 🖼️")

    @property
    def INVALID_AGE(self):
        return _("⚠️ Age must be a number! 🔢")

    @property
    def INVITE_FRIENDS(self):
        return _(
            "📢 <b>Spread the word!</b>\n\nInvited users: <b>{}</b>\n\nYour invite link:\n<code>{}</code>\n\nHelp grow the kingdom! 👑"
        )

    @property
    def CHANNEL(self):
        return _("📺 <b>Our channel:</b>\n{}")

    # Language
    @property
    def CHANGE_LANG(self):
        return _("🌐 <b>Choose your language:</b>")

    def DONE_CHANGE_LANG(self, language: str):
        return _("✅ Language changed!", locale=language)

    # Complaints and moderation
    @property
    def COMPLAINT(self):
        return _("""
⚠️ <b>Report this profile:</b>

Select a reason:
🔞 Inappropriate content
💰 Spam/Advertising
🔫 Other violation

↩️ Cancel
""")

    @property
    def REPORT_TO_USER(self):
        return """
🚨 <b>COMPLAINT RECEIVED</b>

Reporter: <code>{}</code> (@{})
Reported user: <code>{}</code> (@{})

Reason: {}
"""

    @property
    def REPORT_TO_PROFILE(self):
        return _("✅ <b>Report submitted!</b>\n\nThanks for keeping CONQUEER safe. We'll review this.")

    # Photo editing
    @property
    def PHOTO_EDIT_START(self):
        return _("📸 <b>Upload new photos!</b>\n\nSend up to 3 photos to update your profile.")

    @property
    def PHOTO_UNCHANGED(self):
        return _("📸 Photos unchanged")

    @property
    def PHOTO_NO_UPLOADED(self):
        return _("⚠️ No photos uploaded. Try again!")

    @property
    def PHOTO_SAVE_ERROR(self):
        return _("❌ Error saving photos. Please try again.")

    @property
    def PHOTO_SAVE_FINISH_BUTTON(self):
        return _("✅ Done, save photos")

    @property
    def PHOTO_PROGRESS_TEMPLATE(self):
        return _(
            "📸 Photo {current}/{total} uploaded!\n\nYou can add {remaining} more or tap '{finish_button}'"
        )

    def PHOTO_PROGRESS(self, current: int, total: int = 3):
        remaining = total - current
        finish_button_text = _("✅ Done, save photos")
        return self.PHOTO_PROGRESS_TEMPLATE.format(
            current=current, total=total, remaining=remaining, finish_button=finish_button_text
        )

    def PHOTO_SAVED(self, count: int):
        return _("✅ {} photos saved!").format(count)

    def PHOTO_ALL_UPLOADED(self, count: int = 3):
        return _("✅ All {} photos uploaded!").format(count)

    @property
    def PHOTO_LIMIT_REACHED(self):
        return _("⚠️ Maximum 3 photos! Tap 'Done, save photos' to finish.")

    @property
    def PHOTO_UPLOAD_INSTRUCTION(self):
        return _("📸 Send a photo or choose from the menu")

    @property
    def PHOTO_REQUIRED_FOR_PROFILE(self):
        return _("❌ You need at least 1 photo to create your profile!")

    # NEW: Age Filter Messages
    def AGE_FILTER_START(self, min_age: int = 18, max_age: int = 99):
        return _("""
🎂 <b>Set Your Age Range</b>

Current range: <b>{min_age} - {max_age} years old</b>

Enter the <b>minimum age</b> you want to see (18-99):

Type a number or press ↩️ to cancel.
""").format(min_age=min_age, max_age=max_age)

    def AGE_FILTER_MAX(self, min_age: int):
        return _("""
🎂 <b>Set Your Age Range</b>

Minimum age: <b>{min_age}</b> ✅

Now enter the <b>maximum age</b> (18-99):

Type a number or press ↩️ to cancel.
""").format(min_age=min_age)

    def AGE_FILTER_SET(self, min_age: int, max_age: int):
        return _("""
✅ <b>Age filter set!</b>

You'll now see profiles from <b>{min_age} to {max_age} years old</b>.

Hit 🔍 to start browsing with your new filter!
""").format(min_age=min_age, max_age=max_age)

    @property
    def AGE_FILTER_RESET(self):
        return _("""
🔄 <b>Age filter reset!</b>

Back to automatic age matching based on your age and compatibility.

Hit 🔍 to start browsing!
""")

    @property
    def AGE_FILTER_CANCELLED(self):
        return _("❌ Age filter setup cancelled.")

    @property
    def AGE_FILTER_TOO_LOW(self):
        return _("⚠️ Age must be at least 18. Try again!")

    @property
    def AGE_FILTER_TOO_HIGH(self):
        return _("⚠️ Age must be between 18 and 99. Try again!")

    def AGE_FILTER_INVALID_RANGE(self, min_age: int):
        return _("""
⚠️ Max age must be ≥ min age (<b>{min_age}</b>).

Enter a valid maximum age:
""").format(min_age=min_age)

    @property
    def AGE_FILTER_INVALID_INPUT(self):
        return _("⚠️ Numbers only! Enter an age between 18-99.")


message_text = MessageText()