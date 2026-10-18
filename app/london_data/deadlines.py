"""Wall-clock bounds at external I/O boundaries; late workers cannot publish facts."""
import queue
import threading
import time


def call_until(fn,deadline,on_timeout=None):
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TimeoutError('ABSOLUTE_DEADLINE')
    result=queue.Queue(maxsize=1)
    def work():
        try:result.put((True,fn()))
        except BaseException as exc:result.put((False,exc))
    threading.Thread(target=work,daemon=True,name='b1-bounded-io').start()
    try:ok,value=result.get(timeout=remaining)
    except queue.Empty:
        if on_timeout:
            # Transport close is best effort; never wait past deadline on cleanup.
            threading.Thread(target=on_timeout,daemon=True,name='b1-io-close').start()
        raise TimeoutError('ABSOLUTE_DEADLINE') from None
    if time.monotonic()>deadline:raise TimeoutError('ABSOLUTE_DEADLINE')
    if not ok:raise value
    return value
