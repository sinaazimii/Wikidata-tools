import unittest
from unittest.mock import patch
import requests
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ttl_compare import get_entity_ttl
import unittest
from rdflib import Graph
from rdflib.term import Literal
from ttl_compare import diff_ttls
from ttl_compare import triples_to_sparql
from ttl_compare import format_object_for_sparql
from ttl_compare import replace_prefixes
from ttl_compare import has_prefix
from ttl_compare import main


FULL_PREFIXES_STR = """
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix ontolex: <http://www.w3.org/ns/lemon/ontolex#> .
    @prefix dct: <http://purl.org/dc/terms/> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix wikibase: <http://wikiba.se/ontology#> .
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix schema: <http://schema.org/> .
    @prefix cc: <http://creativecommons.org/ns#> .
    @prefix geo: <http://www.opengis.net/ont/geosparql#> .
    @prefix prov: <http://www.w3.org/ns/prov#> .
    @prefix wd: <http://www.wikidata.org/entity/> .
    @prefix data: <https://www.wikidata.org/wiki/Special:EntityData/> .
    @prefix s: <http://www.wikidata.org/entity/statement/> .
    @prefix ref: <http://www.wikidata.org/reference/> .
    @prefix v: <http://www.wikidata.org/value/> .
    @prefix wdt: <http://www.wikidata.org/prop/direct/> .
    @prefix wdtn: <http://www.wikidata.org/prop/direct-normalized/> .
    @prefix p: <http://www.wikidata.org/prop/> .
    @prefix ps: <http://www.wikidata.org/prop/statement/> .
    @prefix psv: <http://www.wikidata.org/prop/statement/value/> .
    @prefix psn: <http://www.wikidata.org/prop/statement/value-normalized/> .
    @prefix pq: <http://www.wikidata.org/prop/qualifier/> .
    @prefix pqv: <http://www.wikidata.org/prop/qualifier/value/> .
    @prefix pqn: <http://www.wikidata.org/prop/qualifier/value-normalized/> .
    @prefix pr: <http://www.wikidata.org/prop/reference/> .
    @prefix prv: <http://www.wikidata.org/prop/reference/value/> .
    @prefix prn: <http://www.wikidata.org/prop/reference/value-normalized/> .
    @prefix wdno: <http://www.wikidata.org/prop/novalue/> .
    """


class TestGetEntityTTL(unittest.TestCase):

    @patch("ttl_compare.requests.get")
    def test_get_entity_ttl_success(self, mock_get):
        # Mock the response from requests.get
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.text = "mocked TTL content"

        entity_id = "Q42"
        revision_id = "123456"
        result = get_entity_ttl(entity_id, revision_id)

        # Check if the URL was constructed correctly
        expected_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}&flavor=dump"
        mock_get.assert_called_once_with(expected_url)

        # Check if the function returns the correct content
        self.assertEqual(result, "mocked TTL content")

    @patch("ttl_compare.requests.get")
    def test_get_entity_ttl_failure(self, mock_get):
        # Mock the response from requests.get to simulate a failure
        mock_get.side_effect = requests.exceptions.RequestException

        entity_id = "Q42"
        revision_id = "123456"

        with self.assertRaises(requests.exceptions.RequestException):
            get_entity_ttl(entity_id, revision_id)


class TestDiffTTLs(unittest.TestCase):

    def setUp(self):
        self.entity_id = "Q42"
        self.old_ttl = (
            FULL_PREFIXES_STR
            + """
        wd:Q42 wdt:P31 wd:Q5 .
        wd:Q42 wdt:P21 wd:Q6581097 .
        """
        )
        self.new_ttl = (
            FULL_PREFIXES_STR
            + """
        wd:Q42 wdt:P31 wd:Q5 .
        wd:Q42 wdt:P21 wd:Q6581097 .
        wd:Q42 wdt:P569 "1952-03-11"^^xsd:date .
        """
        )

    def test_diff_ttls_addition(self):
        expected_sparql = 'INSERT DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };\n'
        result = diff_ttls(self.old_ttl, self.new_ttl, self.entity_id)
        self.assertIn(expected_sparql.strip(), result.strip())

    def test_diff_ttls_deletion(self):
        old_ttl = self.new_ttl
        new_ttl = """
        @prefix wd: <http://www.wikidata.org/entity/> .
        @prefix wdt: <http://www.wikidata.org/prop/direct/> .
        wd:Q42 wdt:P31 wd:Q5 .
        wd:Q42 wdt:P21 wd:Q6581097 .
        """
        expected_sparql = 'DELETE DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };\n'
        result = diff_ttls(old_ttl, new_ttl, self.entity_id)
        self.assertIn(expected_sparql.strip(), result.strip())

    def test_diff_ttls_no_change(self):
        result = diff_ttls(self.old_ttl, self.old_ttl, self.entity_id)
        self.assertEqual(result.strip(), "")


class TestTriplesToSparql(unittest.TestCase):

    def setUp(self):
        self.entity_id = "Q42"

    def test_triples_to_sparql_insert(self):
        triples = [
            (
                f"wd:{self.entity_id}",
                "wdt:P569",
                Literal("1952-03-11", datatype="http://www.w3.org/2001/XMLSchema#date"),
            ),
            (f"wd:{self.entity_id}", "wdt:P31", "wd:Q5"),
        ]
        expected_sparql = (
            'INSERT DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };\n'
            "INSERT DATA { wd:Q42 wdt:P31 wd:Q5 . };"
        )
        result = triples_to_sparql(triples, "INSERT", self.entity_id)
        self.assertEqual(result.strip(), expected_sparql.strip())

    def test_triples_to_sparql_delete(self):
        triples = [
            (
                f"wd:{self.entity_id}",
                "wdt:P569",
                Literal("1952-03-11", datatype="http://www.w3.org/2001/XMLSchema#date"),
            ),
            (f"wd:{self.entity_id}", "wdt:P31", "wd:Q5"),
        ]
        expected_sparql = (
            'DELETE DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };\n'
            "DELETE DATA { wd:Q42 wdt:P31 wd:Q5 . };"
        )
        result = triples_to_sparql(triples, "DELETE", self.entity_id)
        self.assertEqual(result.strip(), expected_sparql.strip())

    def test_triples_to_sparql_skip_owl(self):
        triples = [
            (
                f"wd:{self.entity_id}",
                "wdt:P569",
                Literal("1952-03-11", datatype="http://www.w3.org/2001/XMLSchema#date"),
            ),
            (
                f"wd:{self.entity_id}",
                "http://www.w3.org/2002/07/owl#someValuesFrom",
                "wd:Q5",
            ),
        ]
        expected_sparql = 'INSERT DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };'
        result = triples_to_sparql(triples, "INSERT", self.entity_id)
        self.assertEqual(result.strip(), expected_sparql.strip())

    def test_triples_to_sparql_skip_non_matching_entity(self):
        triples = [
            (
                f"wd:{self.entity_id}",
                "wdt:P569",
                Literal("1952-03-11", datatype="http://www.w3.org/2001/XMLSchema#date"),
            ),
            ("wd:Q12345", "wdt:P31", "wd:Q5"),
        ]
        expected_sparql = 'INSERT DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };'
        result = triples_to_sparql(triples, "INSERT", self.entity_id)
        self.assertEqual(result.strip(), expected_sparql.strip())

    def test_triples_to_sparql_skip_property_subject(self):
        triples = [
            (
                f"wd:{self.entity_id}",
                "wdt:P569",
                Literal("1952-03-11", datatype="http://www.w3.org/2001/XMLSchema#date"),
            ),
            ("wd:P123", "wdt:P31", "wd:Q5"),
        ]
        expected_sparql = 'INSERT DATA { wd:Q42 wdt:P569 "1952-03-11"^^xsd:date . };'
        result = triples_to_sparql(triples, "INSERT", self.entity_id)
        self.assertEqual(result.strip(), expected_sparql.strip())


class TestFormatObjectForSparql(unittest.TestCase):

    def test_format_literal_with_quotes(self):
        literal = Literal(
            'He said "Hello"', datatype="http://www.w3.org/2001/XMLSchema#string"
        )
        result = format_object_for_sparql(literal, str(literal))
        expected = '"He said \\"Hello\\""^^xsd:string'
        self.assertEqual(result, expected)

    def test_format_language_tagged_literal(self):
        literal = Literal("Bonjour", lang="fr")
        result = format_object_for_sparql(literal, str(literal))
        expected = '"Bonjour"@fr'
        self.assertEqual(result, expected)

    def test_format_literal_with_datatype(self):
        literal = Literal(
            "2023-10-01", datatype="http://www.w3.org/2001/XMLSchema#date"
        )
        result = format_object_for_sparql(literal, str(literal))
        expected = '"2023-10-01"^^xsd:date'
        self.assertEqual(result, expected)

    def test_format_uri(self):
        uri = "http://www.wikidata.org/entity/Q42"
        result = format_object_for_sparql(uri, uri)
        expected = "<http://www.wikidata.org/entity/Q42>"
        self.assertEqual(result, expected)

    def test_format_blank_node(self):
        blank_node = Literal("_:b0")
        result = format_object_for_sparql(blank_node, str(blank_node))
        expected = "_:b0"
        self.assertEqual(result, expected)

    def test_format_prefixed_name(self):
        prefixed_name = "wd:Q42"
        result = format_object_for_sparql(prefixed_name, prefixed_name)
        expected = "wd:Q42"
        self.assertEqual(result, expected)

    def test_format_plain_literal(self):
        literal = Literal("Hello World")
        result = format_object_for_sparql(literal, str(literal))
        expected = '"Hello World"'
        self.assertEqual(result, expected)

    def test_format_literal_with_timezone(self):
        literal = Literal(
            "2023-10-01T12:00:00+00:00",
            datatype="http://www.w3.org/2001/XMLSchema#dateTime",
        )
        result = format_object_for_sparql(literal, str(literal))
        expected = '"2023-10-01T12:00:00Z"^^xsd:dateTime'
        self.assertEqual(result, expected)


class TestReplacePrefixes(unittest.TestCase):

    def test_replace_prefixes_full_uri(self):
        url = "http://www.wikidata.org/entity/Q42"
        expected = "wd:Q42"
        result = replace_prefixes(url)
        self.assertEqual(result, expected)

    def test_replace_prefixes_partial_uri(self):
        url = "http://www.wikidata.org/prop/direct/P31"
        expected = "wdt:P31"
        result = replace_prefixes(url)
        self.assertEqual(result, expected)

    def test_replace_prefixes_no_match(self):
        url = "http://example.org/entity/Q42"
        expected = "http://example.org/entity/Q42"
        result = replace_prefixes(url)
        self.assertEqual(result, expected)

    def test_replace_prefixes_multiple_matches(self):
        url = (
            "http://www.wikidata.org/entity/Q42 http://www.wikidata.org/prop/direct/P31"
        )
        expected = "wd:Q42 wdt:P31"
        result = replace_prefixes(url)
        self.assertEqual(result, expected)

    def test_replace_prefixes_empty_string(self):
        url = ""
        expected = ""
        result = replace_prefixes(url)
        self.assertEqual(result, expected)

    def test_replace_prefixes_mixed_content(self):
        url = "Some text http://www.wikidata.org/entity/Q42 and more text"
        expected = "Some text wd:Q42 and more text"
        result = replace_prefixes(url)
        self.assertEqual(result, expected)


class TestHasPrefix(unittest.TestCase):

    def test_has_prefix_with_valid_prefix(self):
        element = "wd:Q42"
        result = has_prefix(element)
        self.assertTrue(result)

    def test_has_prefix_with_invalid_prefix(self):
        element = "ex:Q42"
        result = has_prefix(element)
        self.assertFalse(result)

    def test_has_prefix_with_empty_string(self):
        element = ""
        result = has_prefix(element)
        self.assertFalse(result)

    def test_has_prefix_with_partial_match(self):
        element = "wdQ42"
        result = has_prefix(element)
        self.assertFalse(result)

    def test_has_prefix_with_mixed_content(self):
        element = "Some text wd:Q42 and more text"
        result = has_prefix(element)
        self.assertFalse(result)

    def test_has_prefix_with_multiple_valid_prefixes(self):
        element = "wd:Q42 wdt:P31"
        result = has_prefix(element.split()[0])
        self.assertTrue(result)
        result = has_prefix(element.split()[1])
        self.assertTrue(result)

    def test_has_prefix_with_no_prefix(self):
        element = "Q42"
        result = has_prefix(element)
        self.assertFalse(result)


class TestMainFunction(unittest.TestCase):

    @patch("ttl_compare.get_entity_ttl")
    @patch("ttl_compare.diff_ttls")
    def test_main_function(self, mock_diff_ttls, mock_get_entity_ttl):
        # Mock the responses from get_entity_ttl
        mock_get_entity_ttl.side_effect = [
            "mocked old TTL content",
            "mocked new TTL content",
        ]
        # Mock the response from diff_ttls
        mock_diff_ttls.return_value = "mocked SPARQL update"

        entity_id = "Q42"
        old_revision_id = 123456
        new_revision_id = 123457
        debug = True

        result = main(entity_id, old_revision_id, new_revision_id, debug)

        # Check if get_entity_ttl was called with the correct arguments
        mock_get_entity_ttl.assert_any_call(entity_id, old_revision_id)
        mock_get_entity_ttl.assert_any_call(entity_id, new_revision_id)

        # Check if diff_ttls was called with the correct arguments
        mock_diff_ttls.assert_called_once_with(
            "mocked old TTL content", "mocked new TTL content", entity_id
        )

        # Check if the function returns the correct content
        self.assertEqual(result, "mocked SPARQL update")

    @patch("ttl_compare.get_entity_ttl")
    @patch("ttl_compare.diff_ttls")
    def test_main_function_with_old_revision_id_zero(
        self, mock_diff_ttls, mock_get_entity_ttl
    ):
        # Mock the response from get_entity_ttl for the new revision
        mock_get_entity_ttl.side_effect = [
            "",  # old_ttl should be empty when old_revision_id is 0
            "mocked new TTL content",
        ]
        # Mock the response from diff_ttls
        mock_diff_ttls.return_value = "mocked SPARQL update"

        entity_id = "Q42"
        old_revision_id = 0
        new_revision_id = 123457
        debug = True

        result = main(entity_id, old_revision_id, new_revision_id, debug)

        # Check if get_entity_ttl was called with the correct arguments
        mock_get_entity_ttl.assert_any_call(entity_id, old_revision_id)
        mock_get_entity_ttl.assert_any_call(entity_id, new_revision_id)

        # Check if diff_ttls was called with the correct arguments
        mock_diff_ttls.assert_called_once_with("", "mocked new TTL content", entity_id)

        # Check if the function returns the correct content
        self.assertEqual(result, "mocked SPARQL update")


if __name__ == "__main__":
    unittest.main()
