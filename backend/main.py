if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", type=str, default=None)
    args, _ = parser.parse_known_args()
    
    if args.message is not None:
        # C'est la petite phrase de test
        print(f"Hello from Python, tu as envoyé : {args.message}")
    else:
        # C'est le démarrage normal de ton application
        main()