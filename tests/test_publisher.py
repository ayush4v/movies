"""Unit tests for Telegram post formatting and inline keyboards."""

from app.bot.publisher import TelegramPublisher
from app.metadata.base import EnrichedMetadata


def test_post_format_matches_specification():
    metadata = EnrichedMetadata(
        title="Oppenheimer",
        year=2023,
        genre="Biography, Drama, History",
        rating="8.9/10",
        quality="4K UHD BluRay x265",
        description="The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.",
        poster_url="https://image.tmdb.org/t/p/w780/oppenheimer.jpg",
    )

    formatted = TelegramPublisher.format_post_text(metadata)

    # Verify exact required layout:
    # 🎬 {TITLE}
    #
    # 📅 Year: {YEAR}
    # 🎭 Genre: {GENRE}
    # ⭐ Rating: {RATING}
    # 🎞 Quality: {QUALITY}
    #
    # 📝 {DESCRIPTION}
    assert "🎬 Oppenheimer" in formatted
    assert "📅 Year: 2023" in formatted
    assert "🎭 Genre: Biography, Drama, History" in formatted
    assert "⭐ Rating: 8.9/10" in formatted
    assert "🎞 Quality: 4K UHD BluRay x265" in formatted
    assert "📝 The story of American scientist" in formatted


def test_inline_keyboard_watch_button():
    share_url = "https://terabox.com/s/sample_share_link"
    keyboard = TelegramPublisher.build_inline_keyboard(share_url)

    assert len(keyboard.inline_keyboard) == 1
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "▶ WATCH VIDEO"
    assert button.url == share_url
