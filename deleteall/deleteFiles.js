const fs = require('fs');
const path = require('path');

function deleteAllFiles(folder) {
  return new Promise((resolve, reject) => {
    fs.readdir(folder, (err, files) => {
      if (err) return reject(err);

      let pending = files.length;
      if (!pending) return resolve();

      files.forEach(file => {
        const filePath = path.join(folder, file);

        fs.stat(filePath, (err, stats) => {
          if (err) return reject(err);

          if (stats.isDirectory()) {
            // recursively delete subfolder
            deleteAllFiles(filePath).then(() => {
              fs.rmdir(filePath, err => {
                if (err) reject(err);
                if (!--pending) resolve();
              });
            }).catch(reject);
          } else {
            // delete file
            fs.unlink(filePath, err => {
              if (err) return reject(err);
              if (!--pending) resolve();
            });
          }
        });
      });
    });
  });
}

module.exports = { deleteAllFiles };
