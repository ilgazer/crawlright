import asyncio

from playwright.async_api import async_playwright

from Crawl import Crawl


async def main():
    async with async_playwright() as playwright:
        target = "https://xkcd.com/"
        asd = await Crawl.create(playwright, target, workers=12, out_dir="files")
        await asd.run()


if __name__ == '__main__':
    asyncio.run(main())
