import asyncio
import os
from asyncio import Task
from typing import Union

from playwright.async_api import Response, Page
from tqdm import tqdm


class Crawl:
    file_seen: set[str]
    travelled: set[str]
    queue: set[str]
    target: str
    out_dir: str
    free_pages: list[Page]

    @classmethod
    async def create(cls, playwright, target: str, out_dir: str, workers=1) -> "Crawl":
        self = cls()

        if target[-1] == "/":
            target = target[:-1]

        if out_dir[-1] == "/":
            out_dir = out_dir[:-1]

        self.file_seen = set()
        self.travelled = set()
        self.queue = {target}
        self.target = target
        self.out_dir = out_dir

        browser = await playwright.chromium.launch()
        self.free_pages = []
        for _ in range(workers):
            page = await browser.new_page()
            page.on("response", self.handle_route)
            self.free_pages.append(page)

        return self

    def save_file(self, url, body):
        file: str = self.out_dir + "/" + url.replace("https://", "")
        if file[-1] == "/":
            file += "index.html"

        os.makedirs(file[:file.rindex("/")], exist_ok=True)

        with open(file, 'wb') as f:
            f.write(body)

    async def handle_route(self, response: Response) -> None:
        url = response.url
        if response.status == 200 and self.target in url and url not in self.file_seen:
            self.file_seen.add(url)

            body = await response.body()

            self.save_file(url, body)

    async def do(self, page, url) -> tuple[bool, Page, Union[set[str], str]]:
        try:
            await page.goto(url)
            await page.wait_for_timeout(100)

            new_links = set()

            for a_elem in await page.locator("a").all():
                href = await a_elem.get_attribute("href")
                if href and href[0] == "/":
                    new_links.add(self.target + href)
                elif href and self.target in href:
                    new_links.add(href)

            return True, page, new_links
        except Exception as e:
            self.queue.add(url)
            print(e)
            return False, page, url

    async def run(self):
        self.pbar = tqdm(total=1)
        tasks = set()

        while len(self.queue) > 0 or len(tasks) > 0:
            while len(self.queue) > 0 and len(self.free_pages) > 0:
                url = self.queue.pop()
                page = self.free_pages.pop()
                self.travelled.add(url)
                tasks.add(Task(self.do(page, url)))
                self.queue -= self.travelled

            if len(tasks) == 0:
                break

            dones, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            tasks = pending

            for done in dones:
                success, page, new_links_or_url = done.result()
                self.free_pages.append(page)

                if success:
                    self.queue.update(new_links_or_url - self.travelled)
                else:
                    self.queue.add(new_links_or_url)

            self.pbar.total = len(self.travelled) + len(self.queue)  # Reset and update total
            self.pbar.n = len(self.travelled)  # Re-apply progress
            self.pbar.refresh()  # Redraw the progressbar

        if len(tasks) > 0:
            await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
