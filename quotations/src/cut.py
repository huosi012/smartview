import sys, time
from PIL import Image
from rembg import new_session, remove
A, O = sys.argv[1], sys.argv[2]
names = sys.argv[3].split(',')
sess = new_session('birefnet-general')
for n in names:
    t = time.time()
    im = Image.open(f'{A}/{n}.jpg').convert('RGB')
    out = remove(im, session=sess, post_process_mask=True)
    out.save(f'{O}/{n}.png')
    bb = out.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox()
    print(n, im.size, 'bbox', bb, f'{time.time()-t:.1f}s', flush=True)
