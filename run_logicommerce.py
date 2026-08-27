import os
import subprocess
import sys


def run_step(title, command):

    print()
    print("=" * 60)
    print(title)
    print("=" * 60)

    result = subprocess.run(
        command,
        shell=True
    )

    if result.returncode != 0:

        print()
        print(f"❌ Failed: {title}")
        sys.exit(result.returncode)

    print()
    print(f"✅ Completed: {title}")


def main():

    print("=" * 60)
    print("        LOGICOMMERCE AI")
    print("        END-TO-END PIPELINE")
    print("=" * 60)

    run_step(
        "Generating transfer requests",
        "python src\\create_transfer_requests.py"
    )

    run_step(
        "Running final logistics optimizer",
python src\logistics_optimizer.py    )

    print()
    print("=" * 60)
    print("        PIPELINE COMPLETE")
    print("=" * 60)

    print()
    print("Final output:")
    print(
        "data\\logistics_optimization_v11.csv"
    )

    print()
    print("Dashboard:")
    print(
        "streamlit run dashboard\\app.py"
    )


if __name__ == "__main__":
    main()