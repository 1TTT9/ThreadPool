ThreadPool
===========

An example of threadings pools

[updated 2015-02-07] 
 - adopted Producer-Consumer-Mangement model
 - user needs to implement their own function "producer_task" and "consumer_task" for manager to callback itself.
 - press 'q' to quit.
 - Mamanger is responsible for checking every single thread's lifetime and creating a new one when one thread is out-of-fashioned.

