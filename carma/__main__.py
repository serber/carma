import argparse
import sys

from carma import service


def main() -> None:
    parser = argparse.ArgumentParser(prog="carma")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="path to the YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()

    sys.exit(service.run(args.config))


if __name__ == "__main__":
    main()
