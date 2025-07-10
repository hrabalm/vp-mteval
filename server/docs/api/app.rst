Application Core
================

This module contains the main Litestar application setup and configuration.

.. automodule:: server.app
   :members:
   :undoc-members:
   :show-inheritance:

Main Application
----------------

The main application instance is configured with all necessary plugins, middleware, and route handlers.

Key Components:
  * Authentication middleware
  * Template configuration
  * Vite plugin for frontend integration
  * SAQ plugin for background tasks
  * Database transaction management

Functions
---------

.. autofunction:: server.app.provide_transaction
