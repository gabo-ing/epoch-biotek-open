Hi David,

Same instrument here: original Epoch, P/N 7200201, firmware 1.12. I spent yesterday
getting it to read from Python without Gen5, so I can at least answer the read-command
half of your post. I also have the Gen5 capture you were asking for.

It's capability 2064.

Query the `z` capabilities before you build the assay. Mine answers:

| query | meaning | answer |
|---|---|---|
| 2000 | RDOP22 supported | 1 (`1 Protocol V1.00`) |
| 2056 | extra three-digit read field | 0 |
| 2064 | extended optics field | 0 |
| 2138 | carrier speed select | 0 |

The older backend always sends the extended-optics form of the assay record, and 1.12
doesn't have that field. What threw me for an hour is that `D` is accepted. It comes
back with data, so the command looks fine. It's `O` that then refuses, with status
`2D06`.

Take the field out and reads just work. For a single wavelength the body is:

```
01 RR CC RR CC 0001200100001 1001000001 0 00008 WWWW
                                        ^ no '6' here unless 2064 says 1
```

wrapped as 4-digit length, body, 3-digit checksum (byte sum mod 256), and no ETX after
the checksum since the length already says where the record ends. That's the same
framing @rickwierenga used in #1505. I can confirm it's correct on real 1.12 hardware,
which I think was the open question there, since the 1.12 vectors in that PR are
synthetic.

Two other things that cost me time.

You can put several wavelengths in one assay. The last digit of the read-event block is
the count, then one 10-character block per wavelength:

```
11 01 02 08 02 0001200100001 1001000003 0000080260 0000080280 0000080320
                                      ^ three wavelengths
```

Reading 260/280/320 that way took 22.3 s on mine against 44.8 s as three separate
passes.

And the baud rate moves. Mine answered at 9600 one day and 38400 the next, after Gen5
had been driving it. At the wrong rate you get framing noise (`\x7fC\xff\xff` and
similar) that looks exactly like a dead instrument, which is not what you want to see
given what yours is doing. Worth probing a few rates instead of assuming.

The captures are here: https://github.com/gabo-ing/epoch-biotek-open, under `captures/`.
Gen5 1.11.5 driving this reader: startup and the whole `z` sweep, the Take3 plate
calibration, a 16-well nucleic-acid blank at 260/280/320, a full blank-then-read
session, plus Gen5's own exported results for the same reads so you can check any
decoding against them. There's a small reader in `tools/usbpcap_read.py` so you don't
need Wireshark, and it strips the two FTDI modem-status bytes that otherwise show up at
the front of every reply.

The repo is a standalone Take3 quantification tool rather than a PyLabRobot backend. I
needed something a technician could use this week. But the protocol notes are in
`docs/PROTOCOL.md` and it's MIT, so help yourself to anything useful for an Epoch
backend. For what it's worth it agrees with Gen5 to about 0.5% on the same drops,
reading a DNA ladder at around 440 ng/uL.

On the boot problem I'm no use, sorry. Mine has never done that, so anything I said
about `MC Config Memory Cleared` would be invention. What I can tell you from the
captures is that nothing Gen5 sends writes configuration into the reader. Even the
Take3 calibration only reads A2 and H2 at 450 nm and keeps the X/Y offsets on the PC
side. So I didn't find a serial route back to a good config, and I don't think there is
an obvious one. Agilent support is probably the realistic path for that part.

If it helps: my reader is on the desk and working, with Gen5 on a second machine. If
there's a specific exchange you want to see, a command, a capability query, a capture of
something I haven't recorded, tell me what to send and I'll run it and post the bytes.
Cheap for me, and you can't do it right now.

Hope you get it back on its feet. Those wine assays sound more fun than my aphid DNA.
