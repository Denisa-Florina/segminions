// Create React App ignores postcss.config.js by default; "file" mode makes it use it,
// which is how the Tailwind CSS v4 PostCSS plugin gets into the build.
module.exports = {
  style: {
    postcss: {
      mode: 'file',
    },
  },
};
