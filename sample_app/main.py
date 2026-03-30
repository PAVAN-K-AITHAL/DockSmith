import os

def main():
    message = os.environ.get("GREETING", "Hello from Docksmith Default App!")
    print(f"=== SAMPLE APP RUNNING ===")
    print(message)
    print("=========================")

if __name__ == "__main__":
    main()
