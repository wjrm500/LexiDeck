import json
import os
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from app.constant import Language, OpenAIModel
from app.language_element import Definition, SentencePair, Translation
from app.retriever import (
    CollinsWebsiteScraper,
    OpenAIAPIRetriever,
    Retriever,
    RetrieverFactory,
    RetrieverType,
    SpanishDictWebsiteScraper,
    WebsiteScraper,
    WordReferenceWebsiteScraper,
)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_RETRIEVER_DIR = SCRIPT_DIR + "/data/test_retriever/"


@pytest.fixture
def mock_url() -> str:
    return "https://example.com"


@pytest.fixture
def mock_retriever(mock_url: str) -> Retriever:
    class TestRetriever(Retriever):
        available_language_pairs: list[tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        @staticmethod
        def name() -> str:
            return "Test Retriever"

        async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
            return []

    return TestRetriever(language_from=Language.SPANISH, language_to=Language.ENGLISH)


@pytest.fixture
def mock_website_scraper(mock_url: str) -> WebsiteScraper:
    class TestWebsiteScraper(WebsiteScraper):
        available_language_pairs: list[tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        @staticmethod
        def name() -> str:
            return "Test Retriever"

        async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
            return []

    return TestWebsiteScraper(language_from=Language.SPANISH, language_to=Language.ENGLISH)


@pytest.mark.asyncio
async def test_rate_limited(mock_url: str, mock_retriever: Retriever) -> None:
    mock_url = "https://example.com"
    try:
        with aioresponses() as m:
            # Mock rate-limited response
            m.get(mock_url, status=HTTPStatus.TOO_MANY_REQUESTS)
            is_rate_limited = await mock_retriever.rate_limited()
            assert is_rate_limited

            # Mock non rate-limited response
            m.clear()
            m.get(mock_url, status=200)
            is_rate_limited = await mock_retriever.rate_limited()
            assert not is_rate_limited
    finally:
        await mock_retriever.close_session()


def test_standardize(mock_retriever: Retriever) -> None:
    assert mock_retriever._standardize("remove: punctuation!") == "remove punctuation"
    assert mock_retriever._standardize("  remove whitespace  ") == "remove whitespace"
    assert mock_retriever._standardize("Remove Capitalisation") == "remove capitalisation"


def test_retriever_factory():
    collins_retriever = RetrieverFactory.create_retriever(
        retriever_type=RetrieverType.COLLINS,
        language_from=Language.SPANISH,
        language_to=Language.ENGLISH,
    )
    assert isinstance(collins_retriever, CollinsWebsiteScraper)
    with patch("os.getenv", return_value="mock_api_key"):
        openai_retriever = RetrieverFactory.create_retriever(
            retriever_type=RetrieverType.OPENAI,
            language_from=Language.SPANISH,
            language_to=Language.ENGLISH,
        )
    assert isinstance(openai_retriever, OpenAIAPIRetriever)
    spanishdict_retriever = RetrieverFactory.create_retriever(
        retriever_type=RetrieverType.SPANISHDICT,
        language_from=Language.SPANISH,
        language_to=Language.ENGLISH,
    )
    assert isinstance(spanishdict_retriever, SpanishDictWebsiteScraper)
    wordreference_retriever = RetrieverFactory.create_retriever(
        retriever_type=RetrieverType.WORDREFERENCE,
        language_from=Language.SPANISH,
        language_to=Language.ENGLISH,
    )
    assert isinstance(wordreference_retriever, WordReferenceWebsiteScraper)


@pytest.mark.asyncio
async def test_get_soup(mock_url: str, mock_website_scraper: WebsiteScraper) -> None:
    mock_html = "<html><body>Mocked HTML</body></html>"
    try:
        with aioresponses() as m:
            m.get(mock_url, status=200, body=mock_html)
            soup = await mock_website_scraper._get_soup(mock_url)
            assert soup is not None
            assert soup.find("body").text == "Mocked HTML"
    finally:
        await mock_website_scraper.close_session()


@pytest.fixture
def test_word() -> str:
    return "prueba"


@pytest.fixture
def spanish_dict_url(test_word: str) -> str:
    return f"https://www.spanishdict.com/translate/{test_word}?langFrom=es"


@pytest.fixture
def spanish_dict_html() -> str:
    with open(
        TEST_RETRIEVER_DIR + "spanish_dict_website_scraper_test.html", encoding="utf-8"
    ) as fh:
        return fh.read()


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_no_concise_mode(
    test_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    try:
        retriever = SpanishDictWebsiteScraper(
            language_from=Language.SPANISH, language_to=Language.ENGLISH
        )
        retriever.concise_mode = False  # Default is False but setting explicitly for clarity
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    word_to_translate="prueba",
                    part_of_speech="feminine noun",
                    definitions=[
                        Definition(
                            text="test",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="Hay una prueba de matemáticas el miércoles.",
                                    target_sentence="There's a math test on Wednesday.",
                                ),
                                SentencePair(
                                    source_sentence="No pasó la prueba de acceso y tiene que tomar cursos de regularización.",
                                    target_sentence="He didn't pass the entrance examination and has to take remedial courses.",
                                ),
                                SentencePair(
                                    source_sentence="Nos han dado una prueba para hacer en casa.",
                                    target_sentence="We've been given a quiz to do at home.",
                                ),
                            ],
                        ),
                        Definition(
                            text="proof",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="La carta fue la prueba de que su historia era cierta.",
                                    target_sentence="The letter was proof that her story was true.",
                                ),
                                SentencePair(
                                    source_sentence="Te doy este anillo como prueba de mi amor.",
                                    target_sentence="I give you this ring as a token of my love.",
                                ),
                                SentencePair(
                                    source_sentence="Su risa fue la prueba de que ya no estaba enojada.",
                                    target_sentence="Her laugh was a sign that she was no longer mad.",
                                ),
                            ],
                        ),
                        Definition(
                            text="piece of evidence",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="El fiscal no pudo presentar ninguna prueba para condenarlo.",
                                    target_sentence="The prosecution couldn't present a single piece of evidence to convict him.",
                                )
                            ],
                        ),
                    ],
                    retriever=retriever,
                ),
                Translation(
                    word_to_translate="prueba",
                    part_of_speech="plural noun",
                    definitions=[
                        Definition(
                            text="evidence",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="El juez debe pesar todas las pruebas presentadas antes de dictar sentencia.",
                                    target_sentence="The judge must weigh all of the evidence presented before sentencing.",
                                )
                            ],
                        )
                    ],
                    retriever=retriever,
                ),
            ]
    finally:
        await retriever.close_session()


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_concise_mode(
    test_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    retriever = SpanishDictWebsiteScraper(
        language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    retriever.concise_mode = True
    try:
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    word_to_translate="prueba",
                    part_of_speech="feminine noun",
                    definitions=[
                        Definition(
                            text="test",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="Hay una prueba de matemáticas el miércoles.",
                                    target_sentence="There's a math test on Wednesday.",
                                ),
                            ],
                        ),
                        Definition(
                            text="proof",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="La carta fue la prueba de que su historia era cierta.",
                                    target_sentence="The letter was proof that her story was true.",
                                ),
                            ],
                        ),
                    ],
                    retriever=retriever,
                ),
            ]

            # Test that the translations do not include the second quickdef if it is removed from the HTML
            def remove_div_quickdef2_es(html_content: str) -> str:
                soup = BeautifulSoup(html_content, "html.parser")
                div_to_remove = soup.find("div", id="quickdef2-es")
                if div_to_remove:
                    div_to_remove.decompose()
                return str(soup)

            spanish_dict_html = remove_div_quickdef2_es(spanish_dict_html)
            m.clear()
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            retriever._get_soup.cache_clear()
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    word_to_translate="prueba",
                    part_of_speech="feminine noun",
                    definitions=[
                        Definition(
                            text="test",
                            sentence_pairs=[
                                SentencePair(
                                    source_sentence="Hay una prueba de matemáticas el miércoles.",
                                    target_sentence="There's a math test on Wednesday.",
                                ),
                            ],
                        ),
                    ],
                    retriever=retriever,
                ),
            ]
    finally:
        await retriever.close_session()


@pytest.mark.asyncio
async def test_openai_api_retriever() -> None:
    mock_openai_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "translations": [
                                {
                                    "word_to_translate": "hola",
                                    "part_of_speech": "interjection",
                                    "definitions": [
                                        {
                                            "text": "hello",
                                            "sentence_pairs": [
                                                {
                                                    "source_sentence": "Hola, ¿cómo estás?",
                                                    "target_sentence": "Hello, how are you?",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ]
                        }
                    )
                )
            )
        ]
    )

    mock_openai_client = AsyncMock()
    mock_openai_client.chat.completions.create.return_value = mock_openai_response
    with patch("os.getenv", return_value="mock_api_key"):
        retriever = OpenAIAPIRetriever(language_from=Language.SPANISH, language_to=Language.ENGLISH)
    retriever.client = mock_openai_client
    retriever.language = Language.SPANISH
    retriever.model = OpenAIModel.GPT_4_TURBO
    translations = await retriever.retrieve_translations("hola")
    expected_translation = Translation(
        word_to_translate="hola",
        part_of_speech="interjection",
        definitions=[
            Definition(
                text="hello",
                sentence_pairs=[
                    SentencePair(
                        source_sentence="Hola, ¿cómo estás?",
                        target_sentence="Hello, how are you?",
                    )
                ],
            )
        ],
        retriever=retriever,
    )
    assert translations == [expected_translation]


@pytest.mark.asyncio
async def test_collins_website_scraper(test_word: str) -> None:
    collins_url = f"https://www.collinsdictionary.com/dictionary/spanish-english/{test_word}"
    with open(TEST_RETRIEVER_DIR + "collins_website_scraper_test.html", encoding="utf-8") as fh:
        mock_html = fh.read()
    retriever = CollinsWebsiteScraper(language_from=Language.SPANISH, language_to=Language.ENGLISH)
    with aioresponses() as m:
        m.get(collins_url, status=200, body=mock_html)
        translations = await retriever.retrieve_translations(test_word)
        assert translations == [
            Translation(
                word_to_translate="prueba",
                part_of_speech="feminine noun",
                definitions=[
                    Definition(
                        text="proof",
                        sentence_pairs=[
                            SentencePair(
                                source_sentence="esta es una prueba palpable de su incompetencia",
                                target_sentence="this is clear proof of his incompetence",
                            ),
                            SentencePair(
                                source_sentence="es prueba de que tiene buena salud",
                                target_sentence="that proves or shows he’s in good health",
                            ),
                            SentencePair(
                                source_sentence="sin dar la menor prueba de ello",
                                target_sentence="without giving the faintest sign of it",
                            ),
                        ],
                    ),
                    Definition(
                        text="piece of evidence",
                        sentence_pairs=[
                            SentencePair(
                                source_sentence="pruebas",
                                target_sentence="evidence singular",
                            ),
                            SentencePair(
                                source_sentence="el fiscal presentó nuevas pruebas",
                                target_sentence="the prosecutor presented new evidence",
                            ),
                            SentencePair(
                                source_sentence="se encuentran en libertad por falta de pruebas",
                                target_sentence="they were released for lack of evidence",
                            ),
                        ],
                    ),
                    Definition(
                        text="test",
                        sentence_pairs=[
                            SentencePair(
                                source_sentence="la maestra nos hizo una prueba de vocabulario",
                                target_sentence="our teacher gave us a vocabulary test",
                            ),
                            SentencePair(
                                source_sentence="el médico me hizo más pruebas",
                                target_sentence="the doctor did some more tests on me",
                            ),
                            SentencePair(
                                source_sentence="se tendrán que hacer la prueba del SIDA",
                                target_sentence="they’ll have to be tested for AIDS",
                            ),
                        ],
                    ),
                ],
                retriever=retriever,
            ),
        ]


@pytest.mark.asyncio
async def test_word_reference_website_scraper(test_word: str) -> None:
    word_reference_url = f"https://www.wordreference.com/es/en/translation.asp?spen={test_word}"
    with open(
        TEST_RETRIEVER_DIR + "word_reference_website_scraper_test.html", encoding="utf-8"
    ) as fh:
        mock_html = fh.read()
    retriever = WordReferenceWebsiteScraper(
        language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    with aioresponses() as m:
        m.get(word_reference_url, status=200, body=mock_html)
        translations = await retriever.retrieve_translations(test_word)
        assert translations == [
            Translation(
                word_to_translate="prueba",
                part_of_speech="nf",
                definitions=[
                    Definition(
                        text="evidence",
                        sentence_pairs=[
                            SentencePair(
                                source_sentence="La policía científica está analizando la prueba que puede ser decisiva.",
                                target_sentence="Police are analyzing a crucial piece of evidence.",
                            ),
                        ],
                    ),
                    Definition(
                        text="proof",
                        sentence_pairs=[
                            SentencePair(
                                source_sentence="¿Ves? El algodón está limpio. Esa es la prueba de que los azulejos están limpios.",
                                target_sentence="What more proof do you need that she is cheating on you?",
                            ),
                        ],
                    ),
                ],
                retriever=retriever,
            ),
        ]
