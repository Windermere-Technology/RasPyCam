import argparse
from core.process import start_background_process


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        nargs="+",
        default=None,
        dest="config_filepath",
        help="Provide a filepath to the configuration file. If none provided, will use defaults.",
    )
    return parser.parse_args()


def main(args):
    """Main function to start the background process using the provided config file."""
    # If nargs=1 is used, config_filepath will be a list, so we extract the first element
    config_filepath = args.config_filepath if args.config_filepath else None
    print(config_filepath)
    try:
        start_background_process(config_filepath)
    except KeyboardInterrupt:
        print("Server stopped.")


def run():
    """Parse arguments and execute the main function."""
    args = parse_args()
    main(args)


if __name__ == "__main__":
    run()  # pragma: no cover
