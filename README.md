# Simple IIIF u-something

A Dockerized IIIF server relying heavily on ATS for caching both results and underlying resources. Local cache is minimized since it becomes increasingly inefficient as the number of workers increase.

Worst case scenario, nothing can be retrieved from cache: 1,2,3,4,5,6,7,8
Better scenario, resource cached: 1,2,3,6,7,8
Best case scenario, result cached: 1,8

                      ------------            ----------
----------            |          |-----2----->|        |
|        |-----1----->|          |<----3------|        |
| client |            |    ATS   |  (proxy)   | Siiifu |
|        |<----8------|          |-----6----->|        |
----------            |          |<----7------|        |
                      ------------            ----------
                          |  ^
                          4  |
                          |  5
                          v  |
                      ------------
                      |          |
                      | resource |
                      |          |
                      ------------

