import time, queue, threading
from slack_sdk.errors import SlackApiError

class ChannelQueue:
    def __init__(self, client, cooldown = 1.1):
        self.client = client
        self.cooldown = cooldown
        self.q = queue.Queue()
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    
    def _worker(self):
        last = 0.0
        while True:
            fn, kwargs = self.q.get()
            delay = max(0.0, self.cooldown - (time.time() - last))
            if delay > 0: time.sleep(delay)
            try:
                fn(**kwargs)
            except SlackApiError as e:
                if e.response.status_code == 429:
                    wait = int(e.response.headers.get("Retry-After", "1"))
                    time.sleep(wait + 0.1)
                    fn(**kwargs)
                else:
                    pass
            last = time.time()
            self.q.task_done()

    def enqueue(self, fn, **kwargs):
        self.q.put((fn, kwargs))

