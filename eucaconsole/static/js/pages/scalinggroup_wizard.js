/**
 * @fileOverview Create Scaling Group wizard page JS
 * @requires AngularJS
 *
 */

// Scaling Group wizard includes the AutoScale Tag Editor
angular.module('ScalingGroupWizard', ['AutoScaleTagEditor','EucaConsoleUtils', 'TagEditorModule'])
    .controller('ScalingGroupWizardCtrl', function ($scope, $timeout, eucaUnescapeJson, eucaNumbersOnly) {
        $scope.form = $('#scalinggroup-wizard-form');
        $scope.scalingGroupName = '';
        $scope.launchConfig = '';
        $scope.healthCheckType = 'EC2';
        $scope.healthCheckPeriod = 120;
        $scope.minSize = 1;
        $scope.desiredCapacity = 1;
        $scope.maxSize = 1;
        $scope.urlParams = $.url().param();
        $scope.vpcNetwork = '';
        $scope.vpcNetworkName = '';
        $scope.vpcSubnets = [];
        $scope.vpcSubnetNames = '';
        $scope.vpcSubnetList = {};
        $scope.vpcSubnetChoices = {};
        $scope.vpcSubnetZonesMap = {};
        $scope.availZones = '';
        $scope.loadBalancers = '';
        $scope.summarySection = $('.summary');
        $scope.currentStepIndex = 1;
        $scope.isNotValid = true;
        $scope.initChosenSelectors = function () {
            $('#load_balancers').chosen({'width': '100%', search_contains: true});
            $('#availability_zones').chosen({'width': '100%', search_contains: true});
            $('#vpc_subnet').chosen({'width': '100%', search_contains: true});
        };
        $scope.setInitialValues = function () {
            $scope.availZones = $('#availability_zones').val();
            $(document).ready(function () {
                $scope.cleanLaunchConfigOptions();
            });
        };
        $scope.cleanLaunchConfigOptions = function () {
            var launchConfigSelect = $('#launch_config');
            launchConfigSelect.find("option[value='? string: ?']").remove();
            launchConfigSelect.val('').trigger('chosen:updated');  // Clear launch config value on page refresh
        };
        $scope.checkLaunchConfigParam = function () {
            if( $('#hidden_launch_config_input').length > 0 ){
                $scope.launchConfig = $('#hidden_launch_config_input').val();
            }
        };
        $scope.initController = function (optionsJson) {
            var options = JSON.parse(eucaUnescapeJson(optionsJson));
            $scope.vpcSubnetList = options.vpc_subnet_choices_json;
            $scope.vpcNetwork = options.default_vpc_network;
            $scope.initChosenSelectors();
            $scope.setInitialValues();
            $scope.checkLaunchConfigParam();
            $scope.setWatcher();
            $(document).ready(function () {
                $scope.displayLaunchConfigWarning(options.launchconfigs_count);
            });
            // Timeout is needed for the chosen widget to initialize
            $timeout(function () {
                $scope.adjustVPCSubnetSelectAbide();
            }, 500);
        };
        $scope.checkRequiredInput = function () {
            if( $scope.currentStepIndex == 1 ){
                $scope.isNotValid = false;
                if ($scope.scalingGroupName === '' || $scope.scalingGroupName === undefined) {
                    $scope.isNotValid = true;
                } else if ($scope.minSize === '' || $scope.minSize === undefined) {
                    $scope.isNotValid = true;
                } else if ($scope.desiredCapacity === '' || $scope.desiredCapacity === undefined) {
                    $scope.isNotValid = true;
                } else if ($scope.maxSize === '' || $scope.maxSize === undefined ) {
                    $scope.isNotValid = true;
                } else if (!$scope.launchConfig) {
                    $scope.isNotValid = true;
                } else if ($scope.vpcNetwork !== 'None') {
                    if (typeof $scope.vpcSubnets === 'undefined') {
                        $scope.vpcSubnets = [];  // Work around case where vpcSubnets list is undefined
                    }
                    $scope.isNotValid = $scope.vpcSubnets.length === 0;
                }
            }else if( $scope.currentStepIndex == 2 ){
                $scope.isNotValid = false;
                if( $scope.healthCheckPeriod === '' || $scope.healthCheckPeriod === undefined ){
                    $scope.isNotValid = true;
                }else if( $scope.availZones === '' || $scope.availZones === undefined ){
                    $scope.isNotValid = true;
                }
            }
        };
        $scope.setWatcher = function (){
            $scope.watchCapacityEntries();
            $scope.$watch('currentStepIndex', function(){
                 $scope.setWizardFocus($scope.currentStepIndex);
            });
            $scope.$watch('scalingGroupName', function(){
                $scope.checkRequiredInput();
            });
            $scope.$watch('launchConfig', function(){
                $scope.checkRequiredInput();
            });
            $scope.$watch('healthCheckPeriod', function (newVal) {
                if(newVal) {
                    $scope.healthCheckPeriod = eucaNumbersOnly(newVal);
                    $scope.isNotValid = false;
                } else {
                    $scope.isNotValid = true;
                }
                $scope.checkRequiredInput();
            });
            $scope.$watch('availZones', function(){
                $scope.checkRequiredInput();
            });
            $scope.$watch('vpcNetwork', function () {
                $scope.updateVPCSubnetChoices();
                $scope.updateSelectedVPCNetworkName();
                $scope.adjustVPCSubnetSelectAbide();
                $scope.checkRequiredInput();
            });
            $scope.$watch('vpcSubnets', function (newVal) {
                if (typeof newVal === 'undefined') {
                    $scope.subnets = [];
                }
                $scope.disableVPCSubnetOptions();
                $scope.updateSelectedVPCSubnetNames();
                $scope.checkRequiredInput();
            }, true);
        };
        $scope.watchCapacityEntries = function () {
            var entries = ['minSize', 'maxSize', 'desiredCapacity'];
            angular.forEach(entries, function (item) {
                $scope.$watch(item, function(newVal) {
                    if (newVal) {
                        $scope[item] = eucaNumbersOnly(newVal);
                        $scope.checkRequiredInput();
                    } else {
                        $scope.checkRequiredInput();
                    }
                });
            });
        };
        $scope.adjustVPCSubnetSelectAbide = function () {
            // If VPC option is not chosen, remove the 'required' attribute
            // from the VPC subnet select field and set the value to be 'None'
            if ($scope.vpcNetwork == 'None') {
                $('#vpc_subnet').removeAttr('required');
                $('#vpc_subnet').find('option').first().attr("selected",true);
            } else {
                $('#vpc_subnet').find('option').first().removeAttr("selected");
                $('#vpc_subnet').attr("required", "required");
            }
        };
        $scope.updateVPCSubnetChoices = function () {
            var foundVPCSubnets = false;
            $scope.vpcSubnetChoices = {};
            $scope.vpcSubnets = [];
            angular.forEach($scope.vpcSubnetList, function (subnet) {
                if (subnet.vpc_id === $scope.vpcNetwork) {
                    $scope.vpcSubnetChoices[subnet.id] = 
                        subnet.cidr_block + ' (' + subnet.id + ') | ' + subnet.availability_zone;
                    foundVPCSubnets = true;
                }
                // Create vpc subnet zone map to use later for disabling options
                $scope.vpcSubnetZonesMap[subnet.id] = subnet.availability_zone;
            }); 
            if (!foundVPCSubnets) {
                // Case of No VPC or no existing subnets, set the default to 'None'
                $scope.vpcSubnetChoices.None = $('#vpc_subnet_empty_option').text();
                $scope.vpcSubnets.push('None');
            }
            // Timeout is need for the chosen widget to react after Angular has updated the option list
            $timeout(function() {
                $('#vpc_subnet').trigger('chosen:updated');
            }, 500);
        };
        // Disable the vpc subnet options if they are in the same zone as the selected vpc subnets
        $scope.disableVPCSubnetOptions = function () {
            $('#vpc_subnet').find('option').each(function() {
                var vpcSubnetID = $(this).attr('value');
                var isDisabled = false;
                angular.forEach($scope.vpcSubnets, function (subnetID) {
                    if ($scope.vpcSubnetZonesMap[vpcSubnetID] == $scope.vpcSubnetZonesMap[subnetID]) {
                        if (vpcSubnetID != subnetID) {
                            isDisabled = true;
                        }
                    }
                }); 
                if (isDisabled) {
                    $(this).attr('disabled', 'disabled'); 
                } else {
                    $(this).removeAttr('disabled');
                }
            });
            // Timeout is need for the chosen widget to react after Angular has updated the option list
            $timeout(function() {
                $('#vpc_subnet').trigger('chosen:updated');
            }, 500);
        };
        $scope.updateSelectedVPCNetworkName = function () {
            var vpcNetworkOptions = $('select#vpc_network option');
            vpcNetworkOptions.each(function () {
                if ($(this).attr('value') == $scope.vpcNetwork) {
                    var vpcNetworkNameArray = $(this).text().split(' ');
                    vpcNetworkNameArray.pop();
                    $scope.vpcNetworkName = vpcNetworkNameArray.join(' ');
                    if ($scope.vpcNetworkName === '') {
                        $scope.vpcNetworkName = $scope.vpcNetwork;
                    }
                } 
            });
        };
        $scope.updateSelectedVPCSubnetNames = function () {
            var foundVPCSubnets = false;
            $scope.vpcSubnetNames = [];
            angular.forEach($scope.vpcSubnets, function (subnetID) {
                angular.forEach($scope.vpcSubnetList, function (subnet) {
                    if (subnetID === subnet.id) {
                       $scope.vpcSubnetNames.push(subnet.cidr_block);
                    }
                });
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
            $scope.form.trigger('validate');
            var currentStep = nextStep - 1,
                tabContent = $scope.form.find('#step' + currentStep),
                invalidFields = tabContent.find('[data-invalid]');
            if (invalidFields.length > 0 || $scope.isNotValid === true) {
                invalidFields.focus();
                $event.preventDefault();
                // Handle the case where the tab was clicked to visit the previous step
                if( $scope.currentStepIndex > nextStep){
                    $scope.currentStepIndex = nextStep;
                    $scope.checkRequiredInput();
                }
                return false;
            }
            // Handle the unsaved tag issue
            var existsUnsavedTag = false;
            $('input.taginput[type!="checkbox"]').each(function(){
                if($(this).val() !== ''){
                    existsUnsavedTag = true;
                }
            });
            if( existsUnsavedTag ){
                $event.preventDefault(); 
                $('#unsaved-tag-warn-modal').foundation('reveal', 'open');
                return false;
            }
            // since above lines affects DOM, need to let that take affect first
            $timeout(function() {
                // If all is well, hide current and show new tab without clicking
                // since clicking invokes this method again (via ng-click) and
                // one ng action must complete before another can start
                var hash = "step"+nextStep;
                $(".tabs").children("dd").each(function() {
                    var link = $(this).find("a");
                    if (link.length !== 0) {
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
                $scope.isHelpExpanded = false;
            });
            $scope.currentStepIndex = nextStep;
            $scope.checkRequiredInput();
            // Unhide step 2 of summary
            if (nextStep === 2) {
                $scope.summarySection.find('.step2').removeClass('hide');
                $timeout(function() {
                    // Workaround for the broken placeholer message issue
                    // Wait until the rendering of the new tab page is complete
                    $('#load_balancers').trigger("chosen:updated");
                });
            }
        };
        $scope.handleSizeChange = function () {
            // Adjust desired/max based on min size change
            if ($scope.desiredCapacity < $scope.minSize) {
                $scope.desiredCapacity = $scope.minSize;
            }
            if ($scope.maxSize < $scope.desiredCapacity) {
                $scope.maxSize = $scope.desiredCapacity;
            }
        };
        $scope.displayLaunchConfigWarning = function (launchConfigCount) {
            if (launchConfigCount === 0) {
                $('#create-warn-modal').foundation('reveal', 'open');
            }
        };
    })
;

