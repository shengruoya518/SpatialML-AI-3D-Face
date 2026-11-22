"""Compatibility entrypoint for the retained face-effect renderer scheduling regression."""
import argparse
from pathlib import Path
from validate_face_effects import validate


def main(output, json_jar):
    validate(output, json_jar)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.json_jar)
