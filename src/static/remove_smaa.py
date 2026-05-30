import re

files = [
    'd:/AWS/anti aws text extractor/src/static/login.html',
    'd:/AWS/anti aws text extractor/src/static/signup.html'
]

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Remove SMAAEffect references
    
    # 1. Imports
    html = html.replace('import { BloomEffect, EffectComposer, EffectPass, RenderPass, SMAAEffect, SMAAPreset } from \'postprocessing\';', 'import { BloomEffect, EffectComposer, EffectPass, RenderPass } from \'postprocessing\';')
    
    # 2. initPasses
    old_init_passes = """  initPasses() {
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.bloomPass = new EffectPass(
      this.camera,
      new BloomEffect({ luminanceThreshold: 0.2, luminanceSmoothing: 0, resolutionScale: 1 })
    );
    const smaaPass = new EffectPass(
      this.camera,
      new SMAAEffect({
        preset: SMAAPreset.MEDIUM,
        searchImage: SMAAEffect.searchImageDataURL,
        areaImage: SMAAEffect.areaImageDataURL
      })
    );
    this.renderPass.renderToScreen = false;
    this.bloomPass.renderToScreen = false;
    smaaPass.renderToScreen = true;
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.bloomPass);
    this.composer.addPass(smaaPass);
  }"""

    new_init_passes = """  initPasses() {
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.bloomPass = new EffectPass(
      this.camera,
      new BloomEffect({ luminanceThreshold: 0.2, luminanceSmoothing: 0, resolutionScale: 1 })
    );
    this.renderPass.renderToScreen = false;
    this.bloomPass.renderToScreen = true;
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.bloomPass);
  }"""
    html = html.replace(old_init_passes, new_init_passes)

    # 3. loadAssets
    old_load_assets = """  loadAssets() {
    const assets = this.assets;
    return new Promise(resolve => {
      const manager = new THREE.LoadingManager(resolve);
      const searchImage = new Image();
      const areaImage = new Image();
      assets.smaa = {};
      searchImage.addEventListener('load', function () {
        assets.smaa.search = this;
        manager.itemEnd('smaa-search');
      });
      areaImage.addEventListener('load', function () {
        assets.smaa.area = this;
        manager.itemEnd('smaa-area');
      });
      manager.itemStart('smaa-search');
      manager.itemStart('smaa-area');
      searchImage.src = SMAAEffect.searchImageDataURL;
      areaImage.src = SMAAEffect.areaImageDataURL;
    });
  }"""
    
    new_load_assets = """  loadAssets() {
    return Promise.resolve();
  }"""
    html = html.replace(old_load_assets, new_load_assets)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
