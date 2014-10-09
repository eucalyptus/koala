/**
 * @fileOverview Launch Instance page JS
 * @requires AngularJS
 *
 */

// Launch Instance page includes the Tag Editor, the Image Picker, BDM editor, and security group rules editor
angular.module('LaunchInstance', ['TagEditor', 'BlockDeviceMappingEditor', 'ImagePicker', 'SecurityGroupRules'])
    .controller('LaunchInstanceCtrl', function ($scope, $http, $timeout) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.launchForm = $('#launch-instance-form');
        $scope.tagsObject = {};
        $scope.imageID = '';
        $scope.imageName = '';
        $scope.imagePlatform = '';
        $scope.imageRootDeviceType = '';
        $scope.urlParams = $.url().param();
        $scope.summarySection = $('.summary');
        $scope.instanceNumber = 1;
        $scope.instanceNames = [];
        $scope.keyPair = '';
        $scope.keyPairChoices = {};
        $scope.newKeyPairName = '';
        $scope.keyPairModal = $('#create-keypair-modal');
        $scope.showKeyPairMaterial = false;
        $scope.isLoadingKeyPair = false;
        $scope.securityGroupsRules = {};
        $scope.securityGroupsIDMap = {};
        $scope.selectedGroupRules = [];
        $scope.securityGroupModal = $('#create-securitygroup-modal');
        $scope.securityGroupForm = $('#create-securitygroup-form');
        $scope.securityGroupChoices = {};
        $scope.newSecurityGroupName = '';
        $scope.isLoadingSecurityGroup = false;
        $scope.currentStepIndex = 1;
        $scope.step1Invalid = true;
        $scope.step2Invalid = true;
        $scope.step3Invalid = true;
        $scope.imageJsonURL = '';
        $scope.isNotValid = true;
        $scope.existsImage = true;
        $scope.imageIDErrorClass = '';
        $scope.imageIDNonexistErrorClass = '';
        $scope.initController = function (securityGroupsRulesJson, keyPairChoices,
                                securityGroupChoices, securityGroupsIDMapJson,
                                imageJsonURL) {
            securityGroupsRulesJson = securityGroupsRulesJson.replace(/__apos__/g, "\'")
                .replace(/__curlyfront__/g, "{").replace(/__curlyback__/g, "}");
            securityGroupChoices = securityGroupChoices.replace(/__apos__/g, "\'")
                .replace(/__curlyfront__/g, "{").replace(/__curlyback__/g, "}");
            securityGroupsIDMapJson = securityGroupsIDMapJson.replace(/__apos__/g, "\'")
                .replace(/__curlyfront__/g, "{").replace(/__curlyback__/g, "}");
            keyPairChoices = keyPairChoices.replace(/__apos__/g, "\'")
                .replace(/__curlyfront__/g, "{").replace(/__curlyback__/g, "}");
            $scope.securityGroupsRules = JSON.parse(securityGroupsRulesJson);
            $scope.keyPairChoices = JSON.parse(keyPairChoices);
            $scope.securityGroupChoices = JSON.parse(securityGroupChoices);
            $scope.securityGroupsIDMap = JSON.parse(securityGroupsIDMapJson);
            $scope.imageJsonURL = imageJsonURL;
            $scope.setInitialValues();
            $scope.updateSelectedSecurityGroupRules();
            $scope.preventFormSubmitOnEnter();
            $scope.watchTags();
            $scope.focusEnterImageID();
            $scope.setWatcher();
        };
        $scope.updateSelectedSecurityGroupRules = function () {
            $scope.selectedGroupRules = $scope.securityGroupsRules[$scope.securityGroup];
        };
        $scope.getSecurityGroupIDByName = function (securityGroupName) {
            return $scope.securityGroupsIDMap[securityGroupName];
        };
        $scope.preventFormSubmitOnEnter = function () {
            $(document).ready(function () {
                $(window).keydown(function(evt) {
                    if (evt.keyCode === 13) {
                        evt.preventDefault();
                    }
                });
            });
        };
        $scope.setInitialValues = function () {
            $('#number').val($scope.instanceNumber);
            $scope.instanceType = 'm1.small';
            $scope.instanceZone = $('#zone').find(':selected').val();
            var lastKeyPair = Modernizr.localstorage && localStorage.getItem('lastkeypair_inst');
            if (lastKeyPair != null && $scope.keyPairChoices[lastKeyPair] !== undefined) {
                $('#keypair').val(lastKeyPair);
            }
            $scope.keyPair = $('#keypair').find(':selected').val();
            var lastSecGroup = Modernizr.localstorage && localStorage.getItem('lastsecgroup_inst');
            if (lastSecGroup != null && $scope.securityGroupChoices[lastSecGroup] !== undefined) {
                $('#securitygroup').val(lastSecGroup);
            }
            $scope.securityGroup = $('#securitygroup').find(':selected').val();
            $scope.imageID = $scope.urlParams['image_id'] || '';
            if( $scope.imageID == '' ){
                $scope.currentStepIndex = 1;
            }else{
                $scope.currentStepIndex = 2;
                $scope.step1Invalid = false;
                $scope.loadImageInfo($scope.imageID);
            }
        };
        $scope.saveOptions = function() {
            if (Modernizr.localstorage) {
                localStorage.setItem('lastkeypair_inst', $('#keypair').find(':selected').val());
                localStorage.setItem('lastsecgroup_inst', $('#securitygroup').find(':selected').val());
            }
        };
        $scope.updateTagsPreview = function () {
            // Need timeout to give the tags time to capture in hidden textarea
            $timeout(function() {
                var tagsTextarea = $('textarea#tags'),
                    tagsJson = tagsTextarea.val(),
                    removeButtons = $('.circle.remove');
                removeButtons.on('click', function () {
                    $scope.updateTagsPreview();
                });
                $scope.tagsObject = JSON.parse(tagsJson);
            }, 300);
        };
        $scope.watchTags = function () {
            var addTagButton = $('#add-tag-btn');
            addTagButton.on('click', function () {
                $scope.updateTagsPreview();
            });
        };
        $scope.checkRequiredInput = function () {
            if( $scope.currentStepIndex == 1 ){ 
                if( $scope.isNotValid == false && $scope.imageID.length < 12 ){
                    // Once invalid ID has been entered, do not enable the button unless the ID length is valid
                    // This prevents the error to be triggered as user is typing for the first time 
                    $scope.isNotValid = true;
                    $scope.imageIDErrorClass = "error";
                }else if( $scope.imageID === '' || $scope.imageID === undefined || $scope.imageID.length == 0 ){
                    // Do not enable the button if the input is empty. However, raise no error message
                    $scope.isNotValid = true;
                    $scope.imageIDErrorClass = "";
                }else if( $scope.imageID.length > 12 ){
                    // If the imageID length is longer then 12, disable the button and raise error message
                    $scope.isNotValid = true;
                    $scope.imageIDErrorClass = "error";
                }else if( $scope.imageID.length >= 4 &&  $scope.imageID.substring(0, 4) != "emi-" && $scope.imageID.substring(0, 4) != "ami-" ){ 
                    // If the imageID length is longer than 4, and they do not consist of "emi-" or "ami-", disable the button and raise error message
                    $scope.isNotValid = true;
                    $scope.imageIDErrorClass = "error";
                }else if( $scope.imageID.length == 12 ){
                    // If the above conditions are met and the image ID length is 12, enable the button
                    $scope.isNotValid = false;
                    $scope.imageIDErrorClass = "";
                }
            }else if( $scope.currentStepIndex == 2 ){
                if( $scope.instanceNumber === '' || $scope.instanceNumber === undefined ){
                    $scope.isNotValid = true;
                }else{
                    $scope.isNotValid = false;
                }
            }else if( $scope.currentStepIndex == 3 ){
                if( $scope.keyPair === '' || $scope.keyPair === undefined ){
                    $scope.isNotValid = true;
                }else{
                    $scope.isNotValid = false;
                }
            }
        };
        $scope.setWatcher = function () {
            $scope.setDialogFocus();
            $scope.$watch('currentStepIndex', function(){
                 $scope.setWizardFocus($scope.currentStepIndex);
            });
            $scope.$watch('imageID', function(newID, oldID){
                // Clear the image ID existence check variables
                $scope.existsImage = true;
                $scope.imageIDNonexistErrorClass = "";
                if (newID != oldID && $scope.imageID.length == 12) {
                    $scope.loadImageInfo(newID);
                }
                $scope.checkRequiredInput();
            });
            $scope.$watch('existsImage', function(newValue, oldValue){
                if( newValue != oldValue &&  $scope.existsImage == false ){
                    $scope.isNotValid = true;
                }
            });
            $scope.$watch('instanceNumber', function(){
                $scope.checkRequiredInput();
            });
            $scope.$watch('keyPair', function(){
                $scope.checkRequiredInput();
            });
            $('#number').on('keyup blur', function () {
                var val = $(this).val();
                if (val > 10) {
                    $(this).val(10);
                }
            });
        };
        $scope.loadImageInfo = function(id) {
            $http({
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                method: 'GET',
                url: $scope.imageJsonURL.replace('_id_', id),
                data: ''
            }).success(function (oData) {
                var item = oData.results;
                $scope.imageName = item.name;
                $scope.imagePlatform = item.platform_name;
                $scope.imageRootDeviceType = item.root_device_type;
                $scope.summarySection.find('.step1').removeClass('hide');
                $scope.$broadcast('setBDM', item.block_device_mapping);
                $scope.existsImage = true;
                $scope.imageIDNonexistErrorClass = "";
            }).error(function (oData) {
                $scope.existsImage = false;
                $scope.imageIDNonexistErrorClass = "error";
            });
        };
        $scope.focusEnterImageID = function () {
            // Focus on "Enter Image ID" field if passed appropriate URL param
            if ($scope.urlParams['input_image_id']) {
                $('#image-id-input').focus();
            }
        };
        $scope.setDialogFocus = function () {
            $(document).on('open', '[data-reveal]', function () {
                // When a dialog opens, reset the progress button status
                $(this).find('.dialog-submit-button').css('display', 'block');                
                $(this).find('.dialog-progress-display').css('display', 'none');                
            });
            $(document).on('opened', '[data-reveal]', function () {
                var modal = $(this);
                modal.find('div.error').removeClass('error');
                var modalID = $(this).attr('id');
                if( modalID.match(/terminate/)  || modalID.match(/delete/) || modalID.match(/release/) ){
                    var closeMark = modal.find('.close-reveal-modal');
                    if(!!closeMark){
                        closeMark.focus();
                    }
                }else{
                    var inputElement = modal.find('input[type!=hidden]').get(0);
                    var modalButton = modal.find('button').get(0);
                    if (!!inputElement) {
                        inputElement.focus();
                    } else if (!!modalButton) {
                        modalButton.focus();
                    }
               }
            });
            $(document).on('submit', '[data-reveal] form', function () {
                // When a dialog is submitted, display the progress button status
                $(this).find('.dialog-submit-button').css('display', 'none');                
                $(this).find('.dialog-progress-display').css('display', 'block');                
            });
            $(document).on('close', '[data-reveal]', function () {
                var modal = $(this);
                modal.find('input[type="text"]').val('');
                modal.find('input:checked').attr('checked', false);
                modal.find('textarea').val('');
                modal.find('div.error').removeClass('error');
                var chosenSelect = modal.find('select');
                if (chosenSelect.length > 0) {
                    chosenSelect.prop('selectedIndex', 0);
                    chosenSelect.chosen();
                }
            });
            $(document).on('closed', '[data-reveal]', function () {
                $scope.setWizardFocus($scope.currentStepIndex);
            });
        };
        $scope.setWizardFocus = function (stepIdx) {
            var modal = $('div').filter("#step" + stepIdx);
            var inputElement = modal.find('input[type!=hidden]').get(0);
            var textareaElement = modal.find('textarea[class!=hidden]').get(0);
            var selectElement = modal.find('select').get(0);
            var modalButton = modal.find('button').get(0);
            if (!!textareaElement){
                textareaElement.focus();
            } else if (!!inputElement) {
                inputElement.focus();
            } else if (!!selectElement) {
                selectElement.focus();
            } else if (!!modalButton) {
                modalButton.focus();
            }
        };
        $scope.visitNextStep = function (nextStep, $event) {
            // Trigger form validation before proceeding to next step
            $scope.launchForm.trigger('validate');
            var currentStep = nextStep - 1,
                tabContent = $scope.launchForm.find('#step' + currentStep),
                invalidFields = tabContent.find('[data-invalid]');
            if (invalidFields.length > 0 || $scope.isNotValid === true) {
                invalidFields.focus();
                $event.preventDefault();
                if( $scope.currentStepIndex > nextStep){
                    $scope.currentStepIndex = nextStep;
                    $scope.checkRequiredInput();
                }
                return false;
            }
            // Handle the unsaved tag issue
            var existsUnsavedTag = false;
            $('input.taginput').each(function(){
                if($(this).val() !== ''){
                    existsUnsavedTag = true;
                }
            });
            if( existsUnsavedTag ){
                $event.preventDefault(); 
                $('#unsaved-tag-warn-modal').foundation('reveal', 'open');
                return false;
            }
            if (nextStep == 2 && $scope.step1Invalid) { $scope.clearErrors(2); $scope.step1Invalid = false; }
            if (nextStep == 3 && $scope.step2Invalid) { $scope.clearErrors(3); $scope.step2Invalid = false; }
            if (nextStep == 4 && $scope.step3Invalid) { $scope.clearErrors(4); $scope.step3Invalid = false; }
            
            // since above lines affects DOM, need to let that take affect first
            $timeout(function() {
                // If all is well, hide current and show new tab without clicking
                // since clicking invokes this method again (via ng-click) and
                // one ng action must complete before another can start
                var hash = "step"+nextStep;
                $(".tabs").children("dd").each(function() {
                    var link = $(this).find("a");
                    if (link.length != 0) {
                        var id = link.attr("href").substring(1);
                        var $container = $("#" + id);
                        $(this).removeClass("active");
                        $container.removeClass("active");
                        if (id == hash || $container.find("#" + hash).length) {
                            $(this).addClass("active");
                            $container.addClass("active");
                        }
                    }
                });
                // Unhide appropriate step in summary
                $scope.summarySection.find('.step' + nextStep).removeClass('hide');
                $scope.currentStepIndex = nextStep;
                $scope.checkRequiredInput();
            },50);
        };
        $scope.clearErrors = function(step) {
            $('#step'+step).find('div.error').each(function(idx, val) {
                $(val).removeClass('error');
            });
        };
        $scope.$on('imageSelected', function($event, item) {
            $scope.imageID = item.id;
            $scope.imageName = item.name;
            $scope.imagePlatform = item.platform_name;
            $scope.imageRootDeviceType = item.root_device_type;
            $scope.summarySection.find('.step1').removeClass('hide');
            $scope.checkRequiredInput();
        });
        $scope.buildNumberList = function () {
            // Return a 1-based list of integers of a given size ([1, 2, ... limit])
            var limit = parseInt($scope.instanceNumber, 10) || 10;
            var result = [];
            for (var i = 1; i <= limit; i++) {
                if (limit <= 10) result.push(i);
            }
            return result;
        };
        $scope.showCreateKeypairModal = function() {
            $scope.showKeyPairMaterial = false;
            var form = $('#launch-instance-form');
            var invalid_attr = 'data-invalid';
            form.removeAttr(invalid_attr);
            $(invalid_attr, form).removeAttr(invalid_attr);
            $('.error', form).not('small').removeClass('error');
            $scope.keyPairModal.foundation('reveal', 'open');
        };
        $scope.downloadKeyPair = function ($event, downloadUrl) {
            $event.preventDefault();
            var form = $($event.target);
            $.generateFile({
                csrf_token: form.find('input[name="csrf_token"]').val(),
                filename: $scope.newKeyPairName + '.pem',
                content: form.find('textarea[name="content"]').val(),
                script: downloadUrl
            });
            $scope.showKeyPairMaterial = false;
            var modal = $scope.keyPairModal;
            modal.foundation('reveal', 'close');
            $scope.newKeyPairName = '';
        };
        $scope.handleKeyPairCreate = function ($event, url) {
            $event.preventDefault();
            var formData = $($event.target).serialize();
            $scope.isLoadingKeyPair = true;
            $http({
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                method: 'POST',
                url: url,
                data: formData
            }).success(function (oData) {
                $scope.showKeyPairMaterial = true;
                $scope.isLoadingKeyPair = false;
                $('#keypair-material').val(oData['payload']);
                // Add new key pair to choices and set it as selected
                $scope.keyPairChoices[$scope.newKeyPairName] = $scope.newKeyPairName;
                $scope.keyPair = $scope.newKeyPairName;
                Notify.success(oData.message);
            }).error(function (oData) {
                $scope.isLoadingKeyPair = false;
                if (oData.message) {
                    Notify.failure(oData.message);
                }
            });
        };
        $scope.handleSecurityGroupCreate = function ($event, url) {
            $event.preventDefault();
            $scope.isLoadingSecurityGroup = true;
            var formData = $($event.target).serialize();
            $scope.securityGroupForm.trigger('validate');
            if ($scope.securityGroupForm.find('[data-invalid]').length) {
                return false;
            }
            $http({
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                method: 'POST',
                url: url,
                data: formData
            }).success(function (oData) {
                $scope.isLoadingSecurityGroup = false;
                // Add new security group to choices and set it as selected
                $scope.securityGroupChoices[$scope.newSecurityGroupName] = $scope.newSecurityGroupName;
                $scope.securityGroup = $scope.newSecurityGroupName;
                $scope.selectedGroupRules = JSON.parse($('#rules').val());
                $scope.securityGroupsRules[$scope.newSecurityGroupName] = $scope.selectedGroupRules;
                // Reset values
                $scope.newSecurityGroupName = '';
                $scope.newSecurityGroupDesc = '';
                $('textarea#rules').val('');
                var modal = $scope.securityGroupModal;
                modal.foundation('reveal', 'close');
                Notify.success(oData.message);
            }).error(function (oData) {
                $scope.isLoadingSecurityGroup = false;
                if (oData.message) {
                    Notify.failure(oData.message);
                }
            });
        };
    })
;

