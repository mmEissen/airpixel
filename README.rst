Airpixel
========

This project allows controling NeoPixel LEDs (and similar individually adressable 
colored LEDs) with python.

NeoPixels require a 
microcontroler to be programmed. This makes prototyping slow, as you
need to compile and upload your code to the microcontroler.

To circumvent this problem, this library uses a static program on a networking
enabled microcontroler (the **server**), which reads messages from UDP, deserializes them into
color values and shows them on the LEDs.

On a separate device (the **client**), the python client can be used to establish a connection,
serialize the color values, and send them to the microcontroller.

The arduino sketch provided in this repo was tested on a ESP2866 microcontroler.

Restrictions
------------

Most of the restrictions are down to the arduino sketch. If you make changes
to fit your needs please consider contributing to this project.

The setup will only work:
    - with an ESP2866
    - with RGBW (4 colors) NeoPixels
    - on a (simple) local network


Client Installation
-------------------

Airpixel requires python 3.6 or higher. You can install the python client from
PyPi with:

.. code-block:: bash

    $ pip install airpixel

Server Installation
-------------------

.. note:: 
    The sketch in this repository was only tested on a ESP2866 microcontroller.
    It depends on the ESP8266WiFi library. With some modifications you may get
    the sketch to run on another networking capable microcontroler as well.

The sketch depends on `NeoPixelBus <https://github.com/Makuna/NeoPixelBus>`_
which can be installed through the arduino library manager. 

Rename the ``config_template.h`` to ``config.h`` and fill in your WIFI name and
password, and The number of LEDs on your strip. For a slight performance boost
turn off the debug mode. However this should not be necesarry in general.

The NeoPixels must be connected to the ``RDX0/GPIO3`` pin. Unfortunately this
cannot be configured.

If everything works correctly (and debug mode is enabled in the ``config.h``)
you should be able to see some output in your serial monitor:

.. code-block::

    SETUP
    WiFi connected.
    ADVERTISING...
    ADVERTISING...
    ADVERTISING...
        ...

