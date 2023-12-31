import abc
import argparse
import csv
import os

from genanki import Model as AnkiModel
from genanki import Note as AnkiNote

from app.constant import PrintColour as PC
from app.genanki_extension import load_decks_from_package


class Source(abc.ABC):
    """An abstract base class that represents a source of words to be translated."""

    def _deduplicate(self, words_to_translate: list[str]) -> list[str]:
        """Removes duplicates from a list of words."""
        seen = set()
        unique_words: list[str] = []
        for word in words_to_translate:
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
        return unique_words

    @abc.abstractmethod
    def get_words_to_translate(self) -> list[str]:
        """Abstract method to get a list of words from the source."""
        raise NotImplementedError


class SimpleSource(Source):
    """Source class for getting words from a simple list"""

    words_to_translate: list[str]

    def __init__(self, words_to_translate: list[str]) -> None:
        self.words_to_translate = words_to_translate

    def get_words_to_translate(self) -> list[str]:
        """Simply returns a de-duplicated list of the words provided to the constructor."""
        return self._deduplicate(self.words_to_translate)


class AnkiPackageSource(Source):
    """Source class for getting words from an Anki package."""

    package_path: str
    deck_name: str | None
    field_name: str

    def __init__(
        self, package_path: str, deck_name: str | None = None, field_name: str = "Word"
    ) -> None:
        if not os.path.exists(package_path):
            raise FileNotFoundError(f"Package not found at {package_path}")
        self.package_path = package_path
        self.deck_name = deck_name
        self.field_name = field_name

    def get_words_to_translate(self) -> list[str]:
        """
        Gets words from an Anki package. The words are extracted from the specified deck, and the
        field name is used to determine which field to get the words from for each note.
        """
        decks = load_decks_from_package(self.package_path)
        deck = next(
            (d for d in decks if not self.deck_name or d.name == self.deck_name), None
        )  # If no deck name is specified, use the first deck
        if not deck:
            raise ValueError(f"Deck '{self.deck_name}' not found in package")
        if len(deck.notes) == 0:
            raise ValueError(f"Deck '{deck.name}' has no notes")
        signal_note: AnkiNote = deck.notes[0]
        model: AnkiModel = signal_note.model
        model_field_names = [f["name"]["name"] for f in model.fields]
        if self.field_name not in model_field_names:
            raise ValueError(
                f"Field '{self.field_name}' not found in model. Available fields: {model_field_names}"
            )
        field_index = model_field_names.index(self.field_name)
        words_to_translate = []
        for note in deck.notes:
            assert isinstance(note, AnkiNote)
            words_to_translate.append(note.fields[field_index])
        return self._deduplicate(words_to_translate)


class CSVSource(Source):
    """Source class for getting words from a CSV file."""

    file_path: str
    skip_first_row: bool
    col_num: int

    def __init__(self, file_path: str, skip_first_row: bool = False, col_num: int = 0) -> None:
        self.file_path = file_path
        self.skip_first_row = skip_first_row
        self.col_num = col_num

    def get_words_to_translate(self) -> list[str]:
        """
        Gets a list of words from a CSV file. The CSV file should have one word per row, with the
        word in the first column.
        """
        words_to_translate = []
        with open(self.file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file)
            if self.skip_first_row:
                next(reader, None)
            for row in reader:
                words_to_translate.append(row[self.col_num])
        return self._deduplicate(words_to_translate)


def main(args: argparse.Namespace) -> None:
    """Gets words from a source and prints them to the console."""
    source: Source
    try:
        if args.words:
            source = SimpleSource(words_to_translate=args.words)
        elif args.anki_package_path and args.anki_deck_name and args.anki_field_name:
            source = AnkiPackageSource(
                package_path=args.anki_package_path,
                deck_name=args.anki_deck_name,
                field_name=args.anki_field_name,
            )
        elif args.csv:
            source = CSVSource(file_path=args.csv)
        else:
            raise ValueError(
                "Must provide either --words, --anki-package-path, --anki-deck-name and --anki-field-name, or --csv"
            )
        print(f"Getting words from {source.__class__.__name__}")
        print()
        words = source.get_words_to_translate()
    except Exception as e:
        print(e)
        return
    print(f"{PC.GREEN}Got {len(words)} words{PC.RESET}")
    print(f"   {PC.YELLOW}{words}{PC.RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest and print words from a source. Provide either --words, --anki-package-path or --csv as a source of words"
    )
    parser.add_argument("--words", nargs="+", default=[], help="Words to translate")
    parser.add_argument(
        "--anki-package-path",
        type=str,
        default="",
        help="Path to Anki package (.apkg) file containing words to translate",
    )
    parser.add_argument(
        "--anki-deck-name",
        type=str,
        default="",
        help="Name of deck inside Anki package containing words to translate",
    )
    parser.add_argument(
        "--anki-field-name",
        type=str,
        default="Word",
        help="Name of field inside note inside deck inside Anki package containing words to translate",
    )
    parser.add_argument(
        "--csv", type=str, default="", help="Path to CSV (.csv) file containing words to translate"
    )
    parser.add_argument(
        "--skip-first-row",
        action="store_true",
        help="Skip first row in CSV (.csv) file containing words to transdlate",
    )
    parser.add_argument(
        "--col-num",
        type=int,
        default=0,
        help="Column number in CSV (.csv) file containing words to translate",
    )

    args = parser.parse_args()
    main(args)
