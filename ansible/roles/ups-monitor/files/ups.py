#!/opt/ups-venv/bin/python3

import sys
from discord_webhook import DiscordWebhook

text = ' '.join(sys.argv[1:])

allowed_mentions = {
    "users": ["3710"]
}

w = DiscordWebhook(url='https://discord.com/api/webhooks/1040682980596785262/SqPtejNP7_WEeHPao0_q9PbdiSOCg_RV3QWqpgURUMcYSSBuqeoMgv7msSPcPr2kSfOI', content="@everyone " + text, allowed_mentions=allowed_mentions)
w.execute()

