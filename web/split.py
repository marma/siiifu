#!/usr/bin/env python3

from PIL import Image,ImageFilter
from math import log2
from sys import argv,stdin

def split(fname, dir, min_n):
    with Image.open(fname) as i:
        max_n=int(min(log2(i.width), log2(i.height)))

        for n in reversed(range(min_n, max_n+1)):
            size = 2 ** n

            for x in range(0, int(i.width/size) + 1):
                for y in range(0, int(i.height/size) + 1):
                    offset_x = size * x
                    offset_y = size * y
                    width = min(size, i.width - offset_x)
                    height = min(size, i.height - offset_y)

                    yield (size,
                           offset_x,
                           offset_y, 
                           width, 
                           height, 
                           #i.crop((offset_x, offset_y, offset_x + width-1, offset_y + height-1)).resize((int((2**min_n * width)/size), int((2**min_n*height)/size))).filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=3)))
                           i.crop((offset_x, offset_y, offset_x + width-1, offset_y + height-1)).resize((int((2**min_n * width)/size), int((2**min_n*height)/size))))


if __name__ == "__main__":
    if len(argv) != 4:
        print('usage: <filename> <directory> <min_n>')
        exit(1)

    filename = argv[1]
    directory = argv[2]
    min_n = int(argv[3])

    with stdin.buffer if filename == '-' else open(filename, mode='rb') as f:
        for (size, x, y, w, h, i) in split(f, directory, min_n):
            f = '%s/tile-%d-%d-%d-%d-%d.jpg' % (argv[2], size, x, y, w, h)
            print(f)
            i.save(f, icc_profile=i.info.get('icc_profile'), quality=90, optimize=True, progressive=True)

