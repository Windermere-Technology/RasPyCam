import unittest
from unittest.mock import patch, MagicMock
import main  # type: ignore


# Test the Argument Parser
class TestArgParser(unittest.TestCase):
    @patch("main.argparse.ArgumentParser.parse_args")
    def test_parse_args_with_config(self, mock_parse_args):
        """Test parsing command line arguments with a config file."""
        mock_args = MagicMock()
        mock_args.config_filepath = "config.json"
        mock_parse_args.return_value = mock_args

        args = main.parse_args()

        self.assertEqual(args.config_filepath, "config.json")

    @patch("main.argparse.ArgumentParser.parse_args")
    def test_parse_args_without_config(self, mock_parse_args):
        """Test parsing command line arguments with no config file."""
        mock_args = MagicMock()
        mock_args.config_filepath = None
        mock_parse_args.return_value = mock_args

        args = main.parse_args()

        self.assertIsNone(args.config_filepath)


# Test the Main Function Logic
class TestMainFunction(unittest.TestCase):
    @patch("main.start_background_process")
    def test_main_function_with_valid_config(self, mock_start_process):
        """Test main function with a valid config file."""
        mock_args = MagicMock()
        mock_args.config_filepath = "config.json"

        main.main(mock_args)

        mock_start_process.assert_called_once_with("config.json")

    @patch("main.start_background_process")
    def test_main_function_with_default_config(self, mock_start_process):
        """Test main function with no config file provided (defaults)."""
        mock_args = MagicMock()
        mock_args.config_filepath = None

        main.main(mock_args)

        mock_start_process.assert_called_once_with(None)

    @patch("main.start_background_process")
    def test_main_function_keyboard_interrupt(self, mock_start_process):
        """Test main function handling KeyboardInterrupt."""
        mock_args = MagicMock()
        mock_args.config_filepath = "config.json"

        mock_start_process.side_effect = KeyboardInterrupt

        with patch("builtins.print") as mock_print:
            main.main(mock_args)

            mock_print.assert_any_call("config.json")
            mock_print.assert_any_call("Server stopped.")

            self.assertEqual(mock_print.call_count, 2)
            mock_print.assert_called_with("Server stopped.")


# Test the __main__ Block
class TestMainExecution(unittest.TestCase):
    @patch("main.start_background_process")
    @patch("sys.argv", ["main.py", "--config", "config.json"])
    def test_run_with_config(self, mock_start_process):
        """Test running the script with a config file."""
        with patch("builtins.print"):
            main.run()

        mock_start_process.assert_called_once_with(["config.json"])

    @patch("main.start_background_process")
    @patch("sys.argv", ["main.py"])
    def test_run_without_config(self, mock_start_process):
        """Test running the script without a config file."""
        with patch("builtins.print"):
            main.run()

        mock_start_process.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
