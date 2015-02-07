#!/usr/bin
import sys
import os
import time
import subprocess
import hashlib
import atexit
import thread, threading
import Queue
import random
import uuid

if os.name == 'nt':
    import msvcrt
else:
    import termios
    import select


def myout(msg):
    sys.stderr.write(msg)


class WindowsConsoleX:
    def __init__(self):
        pass

    def clear(self):
        #self.console.page()
        sys.stdout.flush()

    def write(self, str):
        print('\r %s' % str)
        #self.console.write(str)

    def sleep_and_input(self, seconds):
        time.sleep(seconds)


class UnixConsole:
    def __init__(self):
        self.fd = sys.stdin
        self.old = termios.tcgetattr(self.fd.fileno())
        new = termios.tcgetattr(self.fd.fileno())
        new[3] = new[3] & ~termios.ICANON
        new[6][termios.VTIME] = 0
        new[6][termios.VMIN] = 1
        termios.tcsetattr(self.fd.fileno(), termios.TCSADRAIN, new)

        atexit.register(self._onexit)

    def _onexit(self):
        termios.tcsetattr(self.fd.fileno(), termios.TCSADRAIN, self.old)

    def clear(self):
        sys.stdout.write('\033[2J\033[0;0H')
        sys.stdout.flush()

    def write(self, str):
        sys.stdout.write(str)
        sys.stdout.flush()

    def sleep_and_input(self, seconds):
        read,_,_ = select.select([self.fd.fileno()], [], [], seconds)
        if len(read) > 0:
            return self.fd.read(1)
        return None


class Worker(threading.Thread):
    taskq = Queue.Queue()
    resultq = Queue.Queue()
    order = threading.Event()
    label = 0
    # order.set()   -> thr_begin_command
    # order.clear() -> thr_halt_command
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = Worker.getname()
        self.flag = threading.Event()
        self.last_updated = time.time()

    @staticmethod
    def getname():
        Worker.label+=1
        slabel = str(Worker.label)
        prefix = ['0'] * (6-len(slabel))
        prefix.extend([x for x in slabel])
        #name = "%s-%s" % (uuid.uuid4(), ''.join(prefix))
        return  "thr-" + ''.join(prefix)

    @staticmethod
    def spawn(class_obj):
        co = class_obj()
        co.setDaemon(True)
        co.flag.set()
        co.start()
        return co

class Consumer(Worker):

    def run(self):
        while self.flag.isSet():
            self.last_updated = time.time()
            #wait for task-start from manager
            if not Worker.order.is_set():
                Worker.order.wait()

            consume_task(self.name, self.flag)

        myout("%s left gracefully\n" % self.name)

class Producer(Worker):

    def run(self):
        while self.flag.isSet():
            self.last_updated = time.time()            
            #wait for task-start from manager
            if not Worker.order.is_set():
                Worker.order.wait()          

            produce_task(self.name, self.flag)

        myout("%s left gracefully\n" % self.name)


def inner_produce_task(thrname, flag):

    #local terminate alert
    if not flag.isSet():
        return

    try:
        cmd = Worker.taskq.get_nowait()

        myout("%s ptask - %s\n" % (thrname, cmd))

        response = '-'
        if cmd == '1':
            response = 'o'
        if cmd == '0':
            response = 'x'

        Worker.taskq.task_done()
        Worker.resultq.put(response)
        time.sleep(0.3)
    except Queue.Empty:
        time.sleep(0.5)
        flag.clear()


def inner_consume_task(thrname, flag):

    #local terminate alert
    if not flag.isSet():
        return

    try:
        cmd = Worker.resultq.get_nowait()

        myout("%s qtask - %s\n" % (thrname, cmd))        

        response = '-'
        if cmd == 'o':
            response = '1'
        if cmd == 'x':
            response = '0'
        Worker.resultq.task_done()
        time.sleep(0.3)
    except Queue.Empty:
        time.sleep(0.5)
        if Worker.taskq.qsize() == 0:
            flag.clear()        


class ThreadManager(object):

    """
    variable:
        num - number of threads(producer): 
            default = 1
        maxnum_consumer - num of consumer threads:
            default = 1
    function:
        cbfunc_producer - callback function to handle producer task
        cbfunc_consumer - callback function to handle consumer task
    """
    def __init__(self, num=1, maxnum_consumer=1, cbfunc_producer=None, cbfunc_consumer=None, accpeted_timewait=30):

        if cbfunc_producer == None or cbfunc_consumer == None:
            myout("[Error] parameter 'cbfunc_consumer' or 'cbfunc_producer' should not be none.")
            return

        global produce_task, consume_task
        self.maxnum_of_producer = num
        self.maxnum_of_consumer = maxnum_consumer
        produce_task = cbfunc_producer
        consume_task = cbfunc_consumer
        self.accpeted_timewait = accpeted_timewait
        self.name = ThreadManager.__class__.__name__

    def update_list(self, list_obj, class_obj):
        list_bads = []
        for i in range(len(list_obj)):
            thr = list_obj[i]
            delay = time.time() - thr.last_updated
            if delay > self.accpeted_timewait:
               list_bads.append[i]        

        for j in list_bads:
            thr = list_obj[j]
            thrname = thr.name
            thr.flag.clear()
            thr.join()
            list_obj.remove(j)
            myout("%s - %s removed." % (self.name, thrname))

            if Woker.taskq.qsize()>0 and class_ob == Producer:
                list_obj.append(Worker.spawn(class_obj))
                thrname = list_obj[-1].name
                myout("%s - %s added." % (self.name, thrname))


    def start(self, list_task):

        for task in list_task:
            Worker.taskq.put(task)

        list_producer = []
        list_consumer = []
        for n, list_obj, class_obj in [(self.maxnum_of_producer, list_producer, Producer), (self.maxnum_of_consumer, list_consumer, Consumer)]:
            for j in range(n):
                list_obj.append(Worker.spawn(class_obj))


        t_start = time.time()
        isRunning = True
        isFinished = False
        Worker.order.set()
        while isRunning:
            try:
                myout("%s- qT/qR/nP/nC (%d/%d/%d/%d) \n" % ( self.name, Worker.taskq.qsize(), Worker.resultq.qsize(), 
                                                         len(list_producer), len(list_consumer) ))

                if (Worker.taskq.qsize()+Worker.resultq.qsize() == 0) and not isFinished:
                    myout("%s  finished, cost: %3.2f(s) \n" %  (self.name, time.time()-t_start) )
                    isFinished = True

                c = console.sleep_and_input(1)
                if c == 'q':
                    isRunning = False

                if not isRunning:
                    for thr in list_producer:
                        Worker.order.clear()

                    for thr in list_producer + list_consumer:
                        thr.flag.clear()
                        thr.join()
                else:
                    for list_obj, class_obj in [(list_producer, Producer), (list_consumer, Consumer)]:
                        self.update_list(list_obj, class_obj)

            except KeyboardInterrupt:
                isRunning = False
                myout("Keyboard Interrupt!")

        myout("%s left gracefully." % self.name)


produce_task = None
consume_task = None
if os.name == 'nt':
    console = WindowsConsoleX()
else:
    console = UnixConsole()

def main():
    ThreadManager(5, cbfunc_producer = inner_produce_task, cbfunc_consumer = inner_consume_task).start([str(random.randint(0,1)) for i in range(1000)])

if __name__ == "__main__":
    main()
