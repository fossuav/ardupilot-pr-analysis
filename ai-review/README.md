# ai-review

Not a PR. The badge that marks Andy's AI review comments on GitHub: the SFD
wordmark in white on an indigo-to-violet rounded square, with two gold
sparkles off the wing tip. Made 2026-11-24.

![badge](ai-review-badge-128.png)

## Files

- `ai-review-badge.svg` - the master, 512x512 viewBox.
- `ai-review-badge-<size>.png` - 512, 256, 128, 64, 40, 32, 24 and 20 px,
  transparent outside the badge.
- `make_badge.py` - regenerates all of the above.

## Using it in a comment

GitHub shows an inline image at the size the tag asks for, so use the 40 px
PNG at 20 px to stay sharp on high-DPI screens:

```html
<img src="https://raw.githubusercontent.com/fossuav/ardupilot-pr-analysis/main/ai-review/ai-review-badge-40.png" width="20" height="20" alt=""> **Andy's AI Review**
```

The URL only works once this directory is pushed to `main`. Moving or
renaming the files breaks the badge in every comment already posted.

## Reproduce

The wordmark comes from `sfd_logo2.png` in the SmallFastDrone repository.
Run with the path to it, from a checkout beside this one:

```sh
python3 make_badge.py ../../smallfastdrone/sfd_logo2.png
```

Colours, wordmark placement and sparkle positions are the constants at the
top of the script. It needs `numpy` and `opencv-python`.
