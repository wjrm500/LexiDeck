import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from genanki import Note as AnkiNote

from dictionary import Dictionary
from genanki_extension import load_decks_from_package
from main import main
from note_creator import NoteCreator, model
from retriever import SpanishDictWebsiteScraper

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


@pytest.mark.asyncio
async def test_main() -> None:
    anki_package_path = os.path.join(SCRIPT_DIR, "test.apkg")
    try:
        # Delete output.apkg if it exists
        if os.path.exists(anki_package_path):
            os.remove(anki_package_path)

        # Run main with mocks
        deck_id = "123456789"
        mock_notes = {
            "hola": [
                AnkiNote(
                    model=model,
                    fields=[
                        deck_id,
                        "hola",  # word_to_translate
                        "<a href='https://www.spanishdict.com/translate/hola?langFrom=es' style='color:red;'>hola</a>",  # word_to_translate_html  # noqa: E501
                        "interjection",  # part_of_speech
                        "<a href='https://www.spanishdict.com/translate/hello?langFrom=en' style='color:green;'>hello</a>",  # definition_html  # noqa: E501
                        "¡Hola! ¿Cómo estás?",  # source_sentences
                        "Hello! How are you?",  # target_sentences
                    ],
                ),
            ],
            "adiós": [
                AnkiNote(
                    model=model,
                    fields=[
                        deck_id,
                        "adiós",  # word_to_translate
                        "<a href='https://www.spanishdict.com/translate/adi%C3%B3s?langFrom=es' style='color:red;'>adiós</a>",  # word_to_translate_html  # noqa: E501
                        "interjection",  # part_of_speech
                        "<a href='https://www.spanishdict.com/translate/goodbye?langFrom=en' style='color:green;'>goodbye</a>",  # definition_html  # noqa: E501
                        "¡Adiós! ¡Nos vemos!",  # source_sentences
                        "Goodbye! See you later!",  # target_sentences
                    ],
                ),
            ],
        }
        note_creator = NoteCreator(
            deck_id=deck_id,
            dictionary=MagicMock(spec=Dictionary),
            concurrency_limit=1,
        )
        note_creator.rate_limited_create_notes = AsyncMock(side_effect=list(mock_notes.values()))
        with patch("main.NoteCreator", return_value=note_creator):
            await main(
                words_to_translate=["hola", "adiós"],
                retriever=MagicMock(spec=SpanishDictWebsiteScraper),
                concurrency_limit=1,
                note_limit=0,
                output_anki_package_path=anki_package_path,
                output_anki_deck_name="Language learning flashcards",
            )

        # Make assertions
        assert os.path.exists(anki_package_path)
        decks = load_decks_from_package(anki_package_path)
        assert len(decks) == 1
        deck = decks[0]
        assert deck.name == "Language learning flashcards"
        assert len(deck.notes) == 2
        for note in deck.notes:
            assert isinstance(note, AnkiNote)
            word_to_translate = note.fields[1]
            assert (
                note.fields[1:] == mock_notes[word_to_translate][0].fields[1:]
            )  # Ignore deck_id as it is random
    finally:
        # Delete output.apkg if it exists
        if os.path.exists(anki_package_path):
            os.remove(anki_package_path)
