// Input: extracted Census cb_2024_us_cd119_500k.zip (see public/maps/districts/README.md).
// Minimal Polygon SHP + DBF reader; no runtime mapping dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const input = process.argv[2];
if (!input) throw new Error('Usage: node scripts/build-district-maps.mjs <extracted-census-directory>');
const stem = path.join(input, 'cb_2024_us_cd119_500k');
const shp = await fs.readFile(stem + '.shp');
const dbf = await fs.readFile(stem + '.dbf');
const codes = Object.fromEntries('01:AL 02:AK 04:AZ 05:AR 06:CA 08:CO 09:CT 10:DE 12:FL 13:GA 15:HI 16:ID 17:IL 18:IN 19:IA 20:KS 21:KY 22:LA 23:ME 24:MD 25:MA 26:MI 27:MN 28:MS 29:MO 30:MT 31:NE 32:NV 33:NH 34:NJ 35:NM 36:NY 37:NC 38:ND 39:OH 40:OK 41:OR 42:PA 44:RI 45:SC 46:SD 47:TN 48:TX 49:UT 50:VT 51:VA 53:WA 54:WV 55:WI 56:WY'.split(' ').map(s => s.split(':')));
const header = dbf.readUInt16LE(8), recordSize = dbf.readUInt16LE(10);
const fields = [];
let fieldOffset = 1;
for (let p = 32; dbf[p] !== 13; p += 32) {
  const name = dbf.subarray(p, p + 11).toString('ascii').replace(/\0.*$/, '');
  const length = dbf[p + 16];
  fields.push({ name, length, offset: fieldOffset });
  fieldOffset += length;
}
function row(index) {
  const start = header + index * recordSize;
  return Object.fromEntries(fields.map(f => [f.name, dbf.subarray(start + f.offset, start + f.offset + f.length).toString('ascii').trim()]));
}
// Douglas-Peucker simplification in projected SVG pixels.
function simplify(points, tolerance = 0.3) {
  if (points.length <= 3) return points;
  const keep = new Set([0, points.length - 1]);
  const stack = [[0, points.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop(), [x, y] = points[a];
    const dx = points[b][0] - x, dy = points[b][1] - y, length = dx * dx + dy * dy;
    let maximum = tolerance * tolerance, furthest = -1;
    for (let i = a + 1; i < b; i++) {
      const t = length ? Math.max(0, Math.min(1, ((points[i][0] - x) * dx + (points[i][1] - y) * dy) / length)) : 0;
      const distance = (points[i][0] - x - t * dx) ** 2 + (points[i][1] - y - t * dy) ** 2;
      if (distance > maximum) { maximum = distance; furthest = i; }
    }
    if (furthest !== -1) { keep.add(furthest); stack.push([a, furthest], [furthest, b]); }
  }
  return [...keep].sort((a,b) => a-b).map(i => points[i]);
}
const states = new Map();
let index = 0;
for (let offset = 100; offset < shp.length; index++) {
  const size = shp.readInt32BE(offset + 4) * 2, start = offset + 8;
  const data = row(index), code = codes[data.STATEFP];
  if (code) {
    if (shp.readInt32LE(start) !== 5) throw new Error('Expected Polygon shapefile');
    const parts = shp.readInt32LE(start + 36), count = shp.readInt32LE(start + 40);
    const starts = Array.from({length: parts}, (_, i) => shp.readInt32LE(start + 44 + i * 4));
    starts.push(count);
    const rings = [];
    for (let part = 0; part < parts; part++) {
      const ring = [];
      for (let i = starts[part]; i < starts[part + 1]; i++) {
        const at = start + 44 + parts * 4 + i * 16;
        let lon = shp.readDoubleLE(at);
        if (code === 'AK' && lon > 0) lon -= 360;
        ring.push([lon, shp.readDoubleLE(at + 8)]);
      }
      rings.push(ring);
    }
    if (!states.has(code)) states.set(code, []);
    states.get(code).push({ district: Number(data.CD119FP), rings });
  }
  offset = start + size;
}
const output = fileURLToPath(new URL('../public/maps/districts/', import.meta.url));
await fs.mkdir(output, {recursive: true});
let total = 0;
for (const [code, districts] of [...states].sort()) {
  const points = districts.flatMap(d => d.rings.flat());
  const minX = Math.min(...points.map(p=>p[0])), maxX = Math.max(...points.map(p=>p[0]));
  const minY = Math.min(...points.map(p=>p[1])), maxY = Math.max(...points.map(p=>p[1]));
  const cosine = Math.cos((minY + maxY) / 2 * Math.PI / 180);
  const width = (maxX - minX) * cosine, height = maxY - minY;
  const scale = Math.min(720 / width, 500 / height);
  const left = (760 - width * scale) / 2, top = (540 - height * scale) / 2;
  const result = { congress: 119, source: 'U.S. Census Bureau, 2024 cartographic boundaries', viewBox: '0 0 760 540', districts: districts.sort((a,b)=>a.district-b.district).map(d => ({district: d.district, path: d.rings.map(ring => {
    const projected = simplify(ring.map(([x,y])=>[left + (x-minX)*cosine*scale, top + (maxY-y)*scale]));
    if (projected.length < 4) return '';
    return projected.map(([x,y],i)=>(i ? 'L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1)).join('') + 'Z';
  }).join('')})) };
  if (result.districts.some(d=>!d.path)) throw new Error('Empty district in ' + code);
  const json = JSON.stringify(result);
  if (json.length > 150 * 1024) throw new Error('Oversize map: ' + code);
  await fs.writeFile(path.join(output, code + '.json'), json + '\n');
  total += districts.length;
}
if (states.size !== 50 || total !== 435) throw new Error(`Unexpected map count: ${states.size} states, ${total} districts`);
console.log(`Generated ${states.size} state maps with ${total} districts.`);
