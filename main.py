def main():
    print(
        "sensor-test backend entrypoint.\n"
        "Run the API with:\n"
        "  uv run uvicorn sensor_test.web.app:app --host 0.0.0.0 --port 8000\n"
    )


if __name__ == "__main__":
    main()
