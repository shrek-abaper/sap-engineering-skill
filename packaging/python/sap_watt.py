"""Watt entry point; all SAP operations live in the shared sap_adt core."""
from sap_adt.cli import main as core_main


def main() -> None:
    core_main(prog_name="sap-watt")


if __name__ == "__main__":
    main()
