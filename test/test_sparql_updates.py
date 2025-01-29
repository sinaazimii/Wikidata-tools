import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sparql_updates import get_wikidata_updates
from sparql_updates import verify_date
from sparql_updates import write_to_file
from sparql_updates import verify_args
from sparql_updates import main
import requests
import argparse
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch, MagicMock
import sys
import os


class TestGetWikidataUpdates(unittest.TestCase):

    @patch("sparql_updates.requests.get")
    def test_get_wikidata_updates_success(self, mock_get):
        # Mock response data
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {
                "recentchanges": [
                    {
                        "title": "Q123",
                        "ids": "123",
                        "sizes": "456",
                        "flags": "edit",
                        "user": "test_user",
                        "timestamp": "2023-10-01T12:00:00Z",
                        "revid": 555,
                        "old_revid": 444,
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Call the function
        start_time = "2023-10-01T00:00:00Z"
        end_time = "2023-10-02T00:00:00Z"
        changes = get_wikidata_updates(start_time, end_time)

        # Assertions
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["title"], "Q123")
        self.assertEqual(changes[0]["user"], "test_user")
        self.assertIsInstance(changes[0]["revid"], int)
        self.assertEqual(changes[0]["revid"], 555)
        self.assertIsInstance(changes[0]["old_revid"], int)
        self.assertEqual(changes[0]["old_revid"], 444)

    @patch("sparql_updates.requests.get")
    def test_get_wikidata_updates_no_changes(self, mock_get):
        # Mock response data
        mock_response = MagicMock()
        mock_response.json.return_value = {"query": {"recentchanges": []}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Call the function
        start_time = "2023-10-01T00:00:00Z"
        end_time = "2023-10-02T00:00:00Z"
        changes = get_wikidata_updates(start_time, end_time)

        # Assertions
        self.assertEqual(len(changes), 0)

    @patch("sparql_updates.requests.get")
    def test_get_wikidata_updates_request_exception(self, mock_get):
        # Mock request exception
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        # Call the function
        start_time = "2023-10-01T00:00:00Z"
        end_time = "2023-10-02T00:00:00Z"
        changes = get_wikidata_updates(start_time, end_time)

        # Assertions
        self.assertIsNone(changes)

    @patch("sparql_updates.requests.get")
    def test_get_wikidata_updates_api_error(self, mock_get):
        # Mock response data with error
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"info": "Some error occurred"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Call the function
        start_time = "2023-10-01T00:00:00Z"
        end_time = "2023-10-02T00:00:00Z"
        changes = get_wikidata_updates(start_time, end_time)

        # Assertions
        self.assertIsNone(changes)


class TestVerifyArgs(unittest.TestCase):

    def setUp(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument("-f", "--file")
        self.parser.add_argument("-l", "--latest", action="store_true")
        self.parser.add_argument("-t", "--type")
        self.parser.add_argument("-n", "--number")
        self.parser.add_argument("-id", "--id")
        self.parser.add_argument("-st", "--start")
        self.parser.add_argument("-et", "--end")
        self.parser.add_argument("-op", "--omit-print", action="store_true")
        self.parser.add_argument("-d", "--debug", action="store_true")

    def test_verify_args_latest_with_start_or_end(self):
        args = self.parser.parse_args(["--latest", "--start", "2023-10-01 00:00:00"])
        self.assertFalse(verify_args(args))

        args = self.parser.parse_args(["--latest", "--end", "2023-10-01 00:00:00"])
        self.assertFalse(verify_args(args))

    def test_verify_args_start_without_end(self):
        args = self.parser.parse_args(["--start", "2023-10-01 00:00:00"])
        self.assertFalse(verify_args(args))

    def test_verify_args_end_without_start(self):
        args = self.parser.parse_args(["--end", "2023-10-01 00:00:00"])
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_type(self):
        args = self.parser.parse_args(["--type", "invalid_type"])
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_file_extension(self):
        args = self.parser.parse_args(["--file", "invalid_file.pdf"])
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_number(self):
        args = self.parser.parse_args(["--number", "0"])
        self.assertFalse(verify_args(args))

        args = self.parser.parse_args(["--number", "501"])
        self.assertFalse(verify_args(args))

        args = self.parser.parse_args(["--number", "invalid_number"])
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_id(self):
        args = self.parser.parse_args(
            ["--id", "invalid_id"]
        )
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_start_date(self):
        args = self.parser.parse_args(
            ["--start", "invalid_date", "--end", "2023-10-01 00:00:00"]
        )
        self.assertFalse(verify_args(args))

    def test_verify_args_invalid_end_date(self):
        args = self.parser.parse_args(
            ["--start", "2023-10-01 00:00:00", "--end", "invalid_date"]
        )
        self.assertFalse(verify_args(args))

    def test_verify_args_start_date_later_than_end_date(self):
        args = self.parser.parse_args(
            ["--start", "2023-10-02 00:00:00", "--end", "2023-10-01 00:00:00"]
        )
        self.assertFalse(verify_args(args))

    def test_verify_args_valid(self):
        args = self.parser.parse_args(
            [
                "--start",
                (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
                "--end",
                (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--latest"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--type", "edit"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--file", "valid_file.ttl"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--number", "5"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--id", "Q123"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--omit-print"])
        self.assertTrue(verify_args(args))

        args = self.parser.parse_args(["--debug"])
        self.assertTrue(verify_args(args))


class TestVerifyDate(unittest.TestCase):

    def test_verify_date_valid(self):
        date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(verify_date(date))

    def test_verify_date_invalid_format(self):
        date = "2023-10-01"
        self.assertFalse(verify_date(date))

    def test_verify_date_too_early(self):
        date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(verify_date(date))

    def test_verify_date_in_future(self):
        date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(verify_date(date))

    def test_verify_date_invalid_day(self):
        date = "2023-10-32 12:00:00"
        self.assertFalse(verify_date(date))

    def test_verify_date_invalid_month(self):
        date = "2023-13-01 12:00:00"
        self.assertFalse(verify_date(date))


class TestWriteToFile(unittest.TestCase):

    @patch("sparql_updates.open", new_callable=unittest.mock.mock_open)
    def test_write_to_file_success(self, mock_open):
        # Mock data
        data = ["Entity change 1", "Entity change 2"]
        # Mock global variables
        file_name = "test_file.ttl"
        prefixes = "PREFIX wd: <http://www.wikidata.org/entity/>\n"

        # Call the function
        write_to_file(data, file_name, prefixes)
        # Assertions
        mock_open.assert_called_once_with(file_name, "w")
        handle = mock_open()
        handle.write.assert_any_call(prefixes)
        handle.write.assert_any_call("\n")
        handle.write.assert_any_call("Entity change 1")
        handle.write.assert_any_call("\n\n")
        handle.write.assert_any_call("Entity change 2")
        handle.write.assert_any_call("\n\n")

    @patch("sparql_updates.open", new_callable=unittest.mock.mock_open)
    def test_write_to_file_io_error(self, mock_open):
        # Mock data
        data = ["Entity change 1", "Entity change 2"]
        # Mock global variables
        file_name = "test_file.ttl"
        prefixes = "PREFIX wd: <http://www.wikidata.org/entity/>\n"

        # Simulate IOError
        mock_open.side_effect = IOError("Unable to open file")

        # Call the function and assert IOError is raised
        with self.assertRaises(IOError):
            write_to_file(data, file_name, prefixes)
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



if __name__ == "__main__":
    unittest.main()





