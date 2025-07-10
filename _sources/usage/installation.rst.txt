Installation
============

We provide only instructions for running the application using Docker Compose.

Installation Steps
------------------

1. Clone the Repository
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/hrabalm/vp-mteval.git
   cd vp-mteval

2. Run in Development mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
