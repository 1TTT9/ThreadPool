import urllib2
import socket
import argparse


from datetime import date

from thread_pool import ThreadManager, Worker, myout
import Queue
import time

"""
reference: 
  http://love-python.blogspot.jp/2008/07/check-status-proxy-address.html
  http://stackoverflow.com/questions/765305/proxy-check-in-python 
"""

with open("urlroot.txt", 'rb') as fd:
    URLSTRING = fd.read().strip('\n')


def is_bad_proxy(proxyaddr):    
    global URLSTRING
    try:
        proxy_handler = urllib2.ProxyHandler({'http': proxyaddr})
        opener = urllib2.build_opener(proxy_handler)
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib2.install_opener(opener)
        req=urllib2.Request(URLSTRING)  # change the URL to test here
        sock=urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        print 'Error code: ', e.code
        return e.code
    except Exception, detail:
        print "ERROR:", detail
        return True
    return False

def load_proxies(fname):

    lines = []
    with open(fname, 'rb') as fd:
        while True:
            line = fd.readline()
            if not line:
                break

            line = line.strip('\n')
            lines.append(line)

    print "number of proxy: %s" % len(lines)
    return lines

def write_outoput(plist):
    
    outfilename = "_".join(["proxy", "status", date.today().strftime("%Y%m%d")]) + ".out"
    with open(outfilename, 'ab+') as fd:
        for proxy in plist:
            fd.write(proxy+"\n")



def proxy_status_check_produce_task(thrname, flag):

    #local terminate alert
    if not flag.isSet():
        return

    try:
        currentProxy = Worker.taskq.get_nowait()

        myout("%s ptask - %s\n" % (thrname, currentProxy))

        if is_bad_proxy(currentProxy):
            print "Bad Proxy %s" % (currentProxy)
        else:
            print "%s is working" % (currentProxy)
            Worker.resultq.put(currentProxy)            

        Worker.taskq.task_done()
        Worker.resultq.put(currentProxy)

    except Queue.Empty:
        time.sleep(0.5)
        flag.clear()




def proxy_status_check_consume_task(thrname, flag):

    #local terminate alert
    if not flag.isSet():
        return

    try:
        currentProxy = Worker.resultq.get_nowait()

        myout("%s qtask - %s\n" % (thrname, currentProxy))

        write_outoput([currentProxy])

        Worker.resultq.task_done()

    except Queue.Empty:
        time.sleep(0.5)
        if Worker.taskq.qsize() == 0:
            flag.clear()


def main():

    timeout = 15

    socket.setdefaulttimeout(timeout)

    parser = argparse.ArgumentParser(prog="py_proxy_status_check")
    parser.add_argument('-f', '--f', help="proxylist filename", default="proxylist.txt", type=str)
    args = parser.parse_args()
    # two sample proxy IPs
    proxyList = load_proxies(args.f)

    ThreadManager(5, cbfunc_producer = proxy_status_check_produce_task, cbfunc_consumer = proxy_status_check_consume_task, accpeted_timewait=timeout*3).start(proxyList)
    """
    goodproxy_addr = []
    proxy_status = []
    socket.setdefaulttimeout(30)
    for currentProxy in proxyList:
        if is_bad_proxy(currentProxy):
            #print "Bad Proxy %s" % (currentProxy)
            proxy_status.append(0)
        else:
            print "%s is working" % (currentProxy)
            proxy_status.append(1)
            goodproxy_addr.append(currentProxy)

    print "checked result -  good/bad: %d/%d" % (sum(proxy_status), len(proxy_status)-sum(proxy_status))
    write_outoput(goodproxy_addr)
    """

if __name__ == '__main__':
    main()