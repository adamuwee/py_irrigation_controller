import datetime

class ElapsedTime:
    def __init__(self, duration : datetime.timedelta):
        self._start_time = datetime.datetime.now()
        self._duration = duration

    def elapsed_time(self) -> datetime.timedelta:
        return datetime.datetime.now() - self._start_time

    def is_elapsed(self):
        return (datetime.datetime.now() - self._start_time) > self._duration
    
    def remaining_time(self) -> datetime.timedelta:
        if self.is_elapsed():
            return datetime.timedelta(seconds=0)
        else:
            return self._duration - self.elapsed_time()