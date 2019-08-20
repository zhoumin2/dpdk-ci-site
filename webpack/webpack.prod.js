const webpack = require('webpack');
const merge = require('webpack-merge');
const common = require('./webpack.common.js');

const banner = "SPDX-License-Identifier: BSD-3-Clause\n" +
               "Developed by UNH-IOL dpdklab@iol.unh.edu."

module.exports = merge(common, {
  mode: 'production',
  devtool: 'source-map',
  plugins: [
    new webpack.BannerPlugin(banner)
  ]
});
