# Simple IIIF u-something

A Dockerized IIIF server relying heavily on ATS for caching both results and underlying resources


                      |----------|            |--------|
|--------|            |          |----------->|        |
|        |----------->|          |<-----------|        |
| client |            |    ATS   |  (proxy)   | Siiifu |
|        |<-----------|          |----------->|        |
|--------|            |          |<-----------|        |
                      |----------|            |--------|
                          |  ^
                          |  |
                          |  |
                          v  |
                      ------------
                      |          |
                      | resource |
                      |          |
                      ------------

