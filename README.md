# Simple IIIF u-something

A Dockerized IIIF server relying heavily on a central cache for caching both results and underlying resources. Local cache is minimized since it becomes increasingly inefficient as the number of workers increase. Locking is performed to avoid "stampeding herd" problem.

Worst case scenario, nothing can be retrieved from cache: 1,2,3,4,5,6,7,9,11
Better scenario, resource cached: 1,2,3,6,7,9,10
Best case scenario, exact result cached: 1,2,8,9,10,11

  ----------      ---------                ----------       -------------       ------------
  |        |--1-->|       |------2-------->|        |---3-->|           |---4-->|          |
  | client |      | NGINX |<-----10--------| Siiifu |       | Worker(s) |       | Resource |
  |        |<-12--|       |<-x-sendfile-9--|        |<--7---|           |<--5---|          |
  ----------      ---------                ----------       -------------       ------------
                     |                         |                  |
                     |                         8                  |
                     |                         |                  |
                     |                         v                  |
                     |                     ---------              |
                     |                     |       |              |
                     ----------11----------| Cache |<------6------|
                                           |       |
                                           ---------

