import queue
# This single global queue will be shared safely between GUI and GNU Radio
MESSAGE_QUEUE = queue.Queue()