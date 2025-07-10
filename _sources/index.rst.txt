.. VP-MTEval documentation master file, created by
   sphinx-quickstart on Sat May 24 17:12:34 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

VP-MTEval Server Documentation
==================================

VP-MTEval is a web-based machine translation evaluation server built with Litestar and React. This documentation covers the server-side components including the API, models, authentication, and various services.

Overview
--------

The VP-MTEval server provides:

* RESTful API for translation evaluation
* Database models for storing translation data
* Background task processing

Quick Start
-----------

To get started with the VP-MTEval server, see the :doc:`usage/installation` guide.

Architecture
------------

The server is built using:

* **Litestar** - Modern Python web framework
* **SQLAlchemy** - Database ORM with async support
* **PostgreSQL** - Primary database
* **SAQ** - Background task queue
* **Vite** - Frontend build tool integration

Apart from the server components, another important component are custom workers
that handle computation of metrics such as BLEU, chrF2, CometKiwi22, MetricX
and others. Inexpensive metrics that can be computed on CPU can be typically
run alongside the server, while the more expensive ones requiring GPUs can be
spawned by users themselves.

Users can also implement their own metrics or write wrappers around existing ones.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   usage/index
   api/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
