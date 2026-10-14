// Synthetic browser workflow tests; install playwright and pngjs to run.
// ANNOTATION_TEST_OUTPUT can preserve fixtures/reports outside research labels.
const fs = require('fs');
const path = require('path');
const os = require('os');
const assert = require('assert/strict');
const { spawn } = require('child_process');
const { chromium } = require('playwright');
const { PNG } = require('pngjs');
const root = path.resolve(__dirname, '..');
const output = process.env.ANNOTATION_TEST_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(), 'straw-annotation-test-'));
fs.mkdirSync(output, { recursive: true });
const fixtures = path.join(output, 'synthetic_images');
const exportsPath = path.join(output, 'synthetic_exports');
fs.mkdirSync(fixtures, { recursive: true });
const width = 128, height = 96;
for (const name of ['synthetic_01.png', 'synthetic_02.png']) {
  const png = new PNG({ width, height });
  for (let i = 0; i < png.data.length; i += 4) {
    png.data[i] = 110; png.data[i + 1] = 145; png.data[i + 2] = 100; png.data[i + 3] = 255;
  }
  fs.writeFileSync(path.join(fixtures, name), PNG.sync.write(png));
}
const server = spawn(process.env.PYTHON || 'python3', [path.join(root, 'annotate.py'), '--images', fixtures, '--output', exportsPath, '--port', '0', '--no-open'], { cwd: root });
let browser;
const checks = [];
function check(name) { checks.push(name); }

async function run() {
  const url = await new Promise((resolve, reject) => {
    let text = '';
    const timer = setTimeout(() => reject(new Error('Annotation test server did not start')), 10000);
    server.stdout.on('data', data => { text += data; const match = text.match(/http:\/\/127\.0\.0\.1:\d+\//); if (match) { clearTimeout(timer); resolve(match[0]); } });
    server.stderr.on('data', data => process.stderr.write(data));
    server.on('exit', code => reject(new Error('Server exited ' + code)));
  });
  const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const executablePath = process.env.ANNOTATION_CHROME || (fs.existsSync(macChrome) ? macChrome : undefined);
  browser = await chromium.launch({ headless: true, executablePath });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, acceptDownloads: true });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  await page.goto(url);
  await page.waitForFunction(() => document.getElementById('image-title').textContent.includes('synthetic_01'));
  assert.equal(await page.locator('.task').count(), 2);
  const originalSession = await page.evaluate(() => session.id);
  check('automatic image-directory loading');
  await page.locator('#annotator').fill('UI_TEST_ONLY');
  await page.locator('#fill-background').click();
  await page.waitForFunction(() => current.label.every(x => x === 0));
  assert.equal(await page.locator('#annotator').isDisabled(), true);
  check('identity lock and background initialization');

  async function rect(cls, x1, y1, x2, y2) {
    if (!await page.locator(`[data-class="${cls}"]`).isVisible()) await page.locator('#more').click();
    await page.locator(`[data-class="${cls}"]`).click();
    await page.keyboard.press('r');
    const box = await page.locator('#canvas').boundingBox();
    await page.mouse.move(box.x + x1 * box.width / width, box.y + y1 * box.height / height);
    await page.mouse.down();
    await page.mouse.move(box.x + x2 * box.width / width, box.y + y2 * box.height / height);
    await page.mouse.up();
  }
  await rect('255', 10, 10, 35, 30);
  assert.equal(await page.evaluate(() => count(current).straw_pixels), 500);
  await page.locator('[data-tool="brush"]').click();
  await page.locator('#brush-number').fill('4');
  await page.locator('#brush-number').press('Tab');
  let box = await page.locator('#canvas').boundingBox();
  await page.mouse.click(box.x + 48, box.y + 45);
  const afterBrush = await page.evaluate(() => count(current).straw_pixels);
  assert(afterBrush > 500);
  await page.locator('#undo').click();
  assert.equal(await page.evaluate(() => count(current).straw_pixels), 500);
  await page.locator('#redo').click();
  assert.equal(await page.evaluate(() => count(current).straw_pixels), afterBrush);
  check('integer brush, rectangle, undo and redo');
  await rect('128', 60, 10, 80, 20);
  await rect('exclude', 0, 0, 10, 10);
  assert.equal(await page.evaluate(() => count(current).uncertain_pixels), 200);
  assert.equal(await page.evaluate(() => count(current).excluded_pixels), 100);
  await rect('restore', 0, 0, 2, 2);
  assert.equal(await page.evaluate(() => count(current).excluded_pixels), 96);
  check('material ambiguity separated from valid ground ROI');
  await rect('64', 90, 10, 100, 20);
  await page.locator('#check-complete').check();
  await page.locator('#complete').click();
  assert.equal(await page.evaluate(() => current.status), 'draft');
  assert.match(await page.locator('#toast').textContent(), /未标/);
  await rect('0', 90, 10, 100, 20);
  await page.locator('[data-class="255"]').click();
  await page.locator('[data-tool="polygon"]').click();
  box = await page.locator('#canvas').boundingBox();
  for (const [x, y] of [[90, 50], [110, 50], [110, 70], [90, 70]]) await page.mouse.click(box.x + x, box.y + y);
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => count(current).straw_pixels), afterBrush + 400);
  check('completion rejects unmarked pixels and polygon paints original pixels');
  const expected = await page.evaluate(() => count(current));
  await page.locator('#more').click();
  await page.locator('#notes').fill('SYNTHETIC TEST ONLY — not human research labels');
  await page.locator('#close-more').click();
  await page.locator('#check-complete').check();
  await page.locator('#complete').click();
  await page.waitForFunction(() => current.file_name.includes('synthetic_02'));
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/export') && response.request().method() === 'POST');
  await page.locator('#export').click();
  const saved = await (await responsePromise).json();
  assert.equal(saved.all_format_checks_pass, true);
  assert.equal(saved.completed, 1);
  const manifest = JSON.parse(fs.readFileSync(path.join(saved.folder, 'manifest.json')));
  const record = manifest.records[0];
  assert.deepEqual(record.statistics, expected);
  assert.equal(record.statistics.coverage_pp, null);
  assert.equal(record.annotator, 'UI_TEST_ONLY');
  assert.equal(record.inspection_confirmation_method, 'combined_checklist');
  assert.deepEqual(record.inspection, {ground_roi_checked:true,full_image_checked:true,human_annotation_confirmed:true});
  const maskBytes = fs.readFileSync(path.join(saved.folder, record.mask_path));
  assert.equal(maskBytes[24], 8); assert.equal(maskBytes[25], 0);
  const labels = PNG.sync.read(maskBytes), roi = PNG.sync.read(fs.readFileSync(path.join(saved.folder, record.valid_roi_path))), train = PNG.sync.read(fs.readFileSync(path.join(saved.folder, record.training_mask_path)));
  let validPixels = 0, foreground = 0, uncertain = 0;
  for (let i = 0; i < labels.data.length; i += 4) {
    const l = labels.data[i], v = roi.data[i], target = train.data[i];
    assert([0, 128, 255].includes(l));
    assert.equal(target, !v || l === 128 ? 255 : l === 255 ? 1 : 0);
    validPixels += v === 255; foreground += v === 255 && l === 255; uncertain += v === 255 && l === 128;
  }
  assert.equal(expected.valid_pixels, validPixels); assert.equal(expected.straw_pixels, foreground); assert.equal(expected.uncertain_pixels, uncertain);
  assert.deepEqual(fs.readFileSync(path.join(saved.folder, record.image_path)), fs.readFileSync(path.join(fixtures, 'synthetic_01.png')));
  check('browser grayscale PNG export independently decoded; source bytes, statistics, ignore mapping and server validation');
  await page.waitForFunction(() => document.getElementById('busy').style.display === 'none');
  await page.reload();
  await page.waitForFunction(() => current && current.file_name.includes('synthetic_02'));
  assert.equal(await page.evaluate(() => tasks.filter(t => t.status === 'completed').length), 1);
  check('refresh restores project and completion');
  const backupPromise = page.waitForResponse(response => response.url().endsWith('/api/export') && response.request().method() === 'POST');
  await page.locator('#more').click();
  await page.locator('#backup').click();
  const backup = await (await backupPromise).json();
  assert.equal(backup.completed, 1); assert.equal(backup.drafts, 1);
  const backupManifest = JSON.parse(fs.readFileSync(path.join(backup.folder, 'manifest.json')));
  assert(backupManifest.records.some(r => r.status === 'draft' && r.mask_path.startsWith('drafts/')));
  check('drafts are isolated in backup');
  await page.waitForFunction(() => document.getElementById('busy').style.display === 'none');
  await page.locator('#package-input').setInputFiles(backup.package);
  await page.waitForFunction(() => session.imported_from_session_id && current?.file_name.includes('synthetic_01'));
  assert.equal(await page.evaluate(() => count(current).straw_pixels), expected.straw_pixels);
  check('research ZIP restores masks and identity without overwriting old session');
  await page.waitForFunction(() => document.getElementById('busy').style.display === 'none');
  await page.locator('#more').click();
  await page.locator('#new-session').click();
  await page.locator('#new-name').fill('UI_SECOND_RATER_TEST_ONLY');
  await page.locator('#confirm-new').click();
  await page.waitForFunction(() => session.annotator === 'UI_SECOND_RATER_TEST_ONLY' && current);
  assert.equal(await page.evaluate(() => count(current).unmarked_pixels), width * height);
  assert.equal(await page.evaluate(() => count(current).straw_pixels), 0);
  assert.equal(await page.evaluate(() => session.role), 'independent_repeat');
  check('independent repeat starts blank with separate identity/session');
  await page.waitForFunction(() => document.getElementById('busy').style.display === 'none');
  await page.locator('#more').click();
  await page.locator('#sessions').selectOption(originalSession);
  await page.waitForFunction(id => session.id === id && current, originalSession);
  await page.locator('.task').first().click();
  await page.waitForFunction(() => current?.file_name.includes('synthetic_01'));
  assert.equal(await page.evaluate(() => count(current).straw_pixels), expected.straw_pixels);
  check('primary masks survive repeat and session switching');
  if (process.env.ANNOTATION_LEGACY_PACKAGE) {
    await page.locator('#package-input').setInputFiles(process.env.ANNOTATION_LEGACY_PACKAGE);
    await page.waitForFunction(() => current?.tool_version === '2.0.0' && current.status === 'completed');
    assert.equal(await page.locator('#check-complete').isChecked(), true);
    check('v2.0 package and prior three checks restore in simplified interface');
  }
  assert.deepEqual(errors, []);
  await page.screenshot({ path: path.join(output, 'synthetic_ui_test.png'), fullPage: true });
  const result = { status: 'passed', checks, browser_errors: errors, completed_bundle: saved.package, backup_bundle: backup.package, synthetic_only: true };
  fs.writeFileSync(path.join(output, 'browser_verification.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}
run().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); server.kill(); });
