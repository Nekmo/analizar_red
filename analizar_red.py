#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Analizar una red en busca de equipos que dispongan de un hostname
"""
import re
import argparse
import subprocess
import ipaddress
import socket
import threading
from Queue import Queue
from operator import attrgetter

class GetHostname(object):
    """Obtener el hostname de una dirección IP.
    
    Attributes:
        ip -- string con dirección IPv4 de la que obtener el hostname
    """
    hostname = ''
    
    def __init__(self, ip, use_nbtstat=False):
        self.ip = ip
        if use_nbtstat:
            self.hostname, self.is_valid = self.nbtstat(ip)
        else:
            self.hostname, self.is_valid = self.gethostbyaddr(ip)
         
    def nbtstat(self, ip):
        output = subprocess.check_output(['nbtstat', '-a', ip])
        output = re.findall('\s+(\w+)\s+\<[0-9A-F]{2}\>\s+.nico', output)
        if output:
            return (output[0], True)
        else:
            return ('', False)

    def gethostbyaddr(self, ip):
        try:
            return (socket.gethostbyaddr(ip)[0], True)
        except socket.herror:
            return ('', False)

    def get_hostame(self):
        """Obtener el hostname para la dirección, si éste se encuentra disponible
        """
        if not self.is_valid:
            raise socket.herror('unknown host')
        return self.hostname
         
    def __lt__(self, other):
        """Para ordenar correctamente las direcciones después, se hará por su
        dirección IP
        """
        return self.ip < other.ip
         
    def __repr__(self):
        if self.is_valid:
            return '%s is "%s"' % (self.ip, self.hostname)
        else:
            return '%s: unknown host' % self.ip
        
    __str__ = __repr__


class GetHostnamesWorker(threading.Thread):
    """Hilo de trabajo para el proceso de la resolución de los hostnames
    
    Attributes:
        queue_addrs -- Queue de direcciones IPv6 en Str a obtener
        results -- Lista en la que introducir el objeto GetHostname
    """
    def __init__(self, queue_addrs, results, nbtstat):
        super(GetHostnamesWorker, self).__init__()
        self.queue_addrs = queue_addrs
        self.nbtstat = nbtstat

    def run(self):
        while True:
            addr = self.queue_addrs.get()
            hostname = GetHostname(addr, self.nbtstat)
            if hostname.is_valid:
                results.append(hostname)
            self.queue_addrs.task_done()

    def stop(self):
        self._stop = True
        
    def stopped(self):
        return self._stop == True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ip',  type=str,
                        help='Una IP con su máscara. Ej. 192.168.1.0/24')
    parser.add_argument('--threads',  dest='threads', type=int, default=10,
                        help='Número de hilos simultáneos analizando la red')
    parser.add_argument('--use-nbtstat',  dest='use_nbtstat', action='store_true',
                        help='Usar comando de cmd nbtstat para obtener el hostname')
    parser.add_argument('--sort-by-hostname',  dest='hostname_sort', action='store_true',
                        help='Ordenar por el hostname en vez de por la IP')
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('El número de hilos debe ser mínimo de 1.')
    queue_addrs = Queue() # Cola de direcciones a analizar
    results = [] # Listado de las direcciones ya analizadas
    try:
        addrs = ipaddress.IPv4Network(unicode(args.ip))
    except ValueError:
        parser.error('Dirección de red inválida.')
    # Coloco en la cola las direcciones
    for addr in addrs:
        addr = str(addr)
        queue_addrs.put(addr)
    # Establezco los hilos con los GetHostnamesWorker que procesarán la cola
    for i in range(args.threads):
        l = GetHostnamesWorker(queue_addrs, results, args.use_nbtstat)
        l.daemon = True
        l.start()
    queue_addrs.join() # Esperar a que la cola esté vacía
    if args.hostname_sort:
        # Ordenamiento por el hostname
        results.sort(key=attrgetter('hostname'))
    else:
        # Ordenamiento por la IP
        results.sort()
    for result in results:
        print(result)