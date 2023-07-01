# Custom Bots

## About

This repository contains the source code for the custom bots that I have created for users on the [Discord](https://discordapp.com/) platform. These bots are written in [Python](https://www.python.org/) using the [discord.py](https://github.com/Rapptz/discord.py) library.

## Usage

To use these bots, you will need to have [Python](https://www.python.org/) installed on your system. You will also need to install the [discord.py](https://github.com/Rapptz/discord.py) library. You can do this by running the following command:

```bash
python3 -m pip install -U discord.py
```

Set the environment variable `MONGO_URI` to the URI of your [MongoDB](https://www.mongodb.com/) database. You can do this by running the following command:

```bash
export MONGO_URI="mongodb://localhost:27017"
```

or by adding the monogo URI in your `.env` file.

Once you have installed the required dependencies, you can run the bots by running the following command:

```bash
python3 bot.py
```

## How to add bot to database

To add a bot to the database, you just need to run the `adder.py` script. You can do this by running the following command:

```bash
python3 adder.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
