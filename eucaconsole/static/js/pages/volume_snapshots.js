/**
 * @fileOverview Volume Snapshots page JS
 * @requires AngularJS
 *
 */

angular.module('VolumeSnapshots', ['TagEditor', 'EucaConsoleUtils'])
    .controller('VolumeSnapshotsCtrl', function ($scope, $http, $timeout, eucaHandleError) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.loading = false;
        $scope.snapshots = [];
        $scope.jsonEndpoint = '';
        $scope.initialLoading = true;
        $scope.deleteFormAction = '';
        $scope.snapshotID = '';
        $scope.snapshotName = '';
        $scope.imagesURL = '';
        $scope.images = undefined;
        $scope.initController = function (jsonEndpoint, imagesURL) {
            $scope.jsonEndpoint = jsonEndpoint;
            $scope.imagesURL = imagesURL;
            $scope.getVolumeSnapshots();
            $scope.setFocus();
        };
        $scope.revealRegisterSnapshotModal = function (snapshot_id) {
            var modal = $('#register-snapshot-modal');
            $scope.snapshotID = snapshot_id;
            modal.foundation('reveal', 'open');
        };
        $scope.revealDeleteModal = function (volume_id, snapshot) {
            var modal = $('#delete-snapshot-modal');
            $scope.volumeID = volume_id;
            $scope.snapshotID = snapshot.id;
            $scope.snapshotName = snapshot.name;
            $scope.images = undefined;
            $scope.getSnapshotImages(snapshot, $scope.imagesURL);
            modal.foundation('reveal', 'open');
        };
        $scope.setFocus = function () {
            $(document).on('opened.fndtn.reveal', '[data-reveal]', function () {
                var modal = $(this);
                var inputElement = modal.find('input[type!=hidden]').get(0);
                var modalButton = modal.find('button').get(0);
                if (!!inputElement) {
                    inputElement.focus();
                } else if (!!modalButton) {
                    modalButton.focus();
                }
            });
        };
        $scope.getVolumeSnapshots = function () {
            $http.get($scope.jsonEndpoint).success(function(oData) {
                var inProgressCount = 0;
                $scope.snapshots = oData ? oData.results : [];
                $scope.initialLoading = false;
                // Detect if any snapshots are in progress
                $scope.snapshots.forEach(function(snapshot) {
                    var progress = parseInt(snapshot.progress.replace('%', ''), 10);
                    if (progress < 100) {
                        inProgressCount += 1;
                    }
                });
                // Auto-refresh snapshots if any of them are in progress
                if (inProgressCount > 0) {
                    $timeout(function() { $scope.getVolumeSnapshots(); }, 4000);  // Poll every 4 seconds
                }
            }).error(function (oData, status) {
                eucaHandleError(oData, status);
            });
        };
        $scope.getSnapshotImages = function (snapshot, url) {
            var urlReplaced = url.replace('_id_', snapshot.id);
            $http.get(urlReplaced).success(function(oData) {
                var results = oData ? oData.results : '';
                if (results && results.length > 0) {
                    $scope.images = results;
                }
            }).error(function (oData, status) {
                eucaHandleError(oData, status);
            });
        };
    })
;

